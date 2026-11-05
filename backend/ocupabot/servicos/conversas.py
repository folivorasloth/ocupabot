"""Conversas, mensagens e a fila de saída."""

from __future__ import annotations

import logging
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import config
from ..dominio.documentos import redigir
from ..enums import Autor, EstadoConversa, StatusEnvio
from ..integracoes.mensageria import Canal, ErroEnvio
from ..modelos import Contato, Conversa, Mensagem
from ..relogio import agora
from . import auditoria, parametros

log = logging.getLogger("ocupabot.conversas")


def contato(s: Session, telefone: str) -> Contato:
    c = s.scalar(select(Contato).where(Contato.telefone == telefone))
    if c is None:
        c = Contato(telefone=telefone)
        s.add(c)
        s.flush()
    return c


def conversa_de(s: Session, c: Contato) -> Conversa:
    conv = s.scalar(select(Conversa).where(Conversa.contato_id == c.id))
    if conv is None:
        conv = Conversa(contato_id=c.id, estado=EstadoConversa.BOT, dados={})
        s.add(conv)
        s.flush()
    return conv


def ja_recebida(s: Session, id_externo: str | None) -> bool:
    return bool(id_externo) and s.scalar(
        select(Mensagem.id).where(Mensagem.id_externo == id_externo)
    ) is not None


def registrar_entrada(s: Session, conv: Conversa, texto: str, id_externo: str | None = None) -> Mensagem | None:
    """Grava a mensagem recebida (com CPF/RG redigidos). None se for repetida."""
    if ja_recebida(s, id_externo):
        return None
    m = Mensagem(conversa_id=conv.id, autor=Autor.CONTATO, texto=redigir(texto)[:4000],
                 id_externo=id_externo, status=StatusEnvio.RECEBIDA, em=agora())
    try:
        with s.begin_nested():
            s.add(m)
    except IntegrityError:
        return None
    conv.ultima_entrada_em = agora()
    return m


def enfileirar(s: Session, conv: Conversa, texto: str, autor: Autor = Autor.BOT,
               usuario_id: int | None = None, simulado: bool = False) -> Mensagem:
    horas = parametros.inteiro(
        s, "resposta_equipe_validade_horas" if autor == Autor.EQUIPE else "resposta_bot_validade_horas"
    )
    m = Mensagem(conversa_id=conv.id, autor=autor, texto=texto, usuario_id=usuario_id,
                 status=StatusEnvio.SIMULADA if simulado else StatusEnvio.PENDENTE,
                 valida_ate=agora() + timedelta(hours=horas), em=agora())
    s.add(m)
    s.flush()
    return m


def pode_falar(telefone: str) -> bool:
    cfg = config()
    return not cfg.modo_teste or telefone in cfg.lista_numeros_teste


def enviar_mensagem(s: Session, m: Mensagem, canal: Canal) -> None:
    conv = s.get(Conversa, m.conversa_id)
    tel = conv.contato.telefone
    if m.valida_ate and agora() > m.valida_ate:
        m.status = StatusEnvio.EXPIRADA
        if m.autor == Autor.BOT and conv.estado == EstadoConversa.BOT:
            passar_para_equipe(s, conv, "resposta do bot não saiu a tempo")
        return
    if not pode_falar(tel):
        m.status = StatusEnvio.BLOQUEADA
        m.erro = "modo teste: número fora da lista"
        return
    m.tentativas += 1
    try:
        m.id_externo = canal.enviar(tel, m.texto) or None
        m.status = StatusEnvio.ENVIADA
        m.erro = None
    except ErroEnvio as e:
        m.erro = str(e)[:300]
        if m.tentativas >= 5:
            m.status = StatusEnvio.FALHOU


def enviar_pendentes(s: Session, canal: Canal, limite: int = 30) -> int:
    pendentes = s.scalars(select(Mensagem).where(Mensagem.status == StatusEnvio.PENDENTE)
                          .order_by(Mensagem.id).limit(limite)).all()
    for m in pendentes:
        enviar_mensagem(s, m, canal)
    return len(pendentes)


# --- Humano no circuito ----------------------------------------------------------------------------

def passar_para_equipe(s: Session, conv: Conversa, motivo: str) -> None:
    conv.estado = EstadoConversa.AGUARDANDO_HUMANO
    conv.motivo_humano = motivo[:200]
    conv.fluxo = conv.etapa = None
    conv.dados = {}
    conv.erros_seguidos = 0


def assumir(s: Session, conv: Conversa, usuario_id: int) -> None:
    antes = auditoria.foto(conv)
    conv.estado = EstadoConversa.HUMANO
    conv.atendente_id = usuario_id
    auditoria.registrar(s, "conversa", conv.id, "assumir", antes, auditoria.foto(conv), usuario_id, "painel")


def devolver(s: Session, conv: Conversa, usuario_id: int) -> None:
    antes = auditoria.foto(conv)
    conv.estado = EstadoConversa.BOT
    conv.atendente_id = None
    conv.motivo_humano = None
    conv.fluxo = conv.etapa = None
    conv.dados = {}
    conv.erros_seguidos = 0
    auditoria.registrar(s, "conversa", conv.id, "devolver", antes, auditoria.foto(conv), usuario_id, "painel")


def responder(s: Session, conv: Conversa, texto: str, usuario_id: int) -> Mensagem:
    if conv.estado != EstadoConversa.HUMANO:
        assumir(s, conv, usuario_id)
    m = enfileirar(s, conv, texto.strip()[:4000], Autor.EQUIPE, usuario_id)
    auditoria.registrar(s, "conversa", conv.id, "responder", None, {"mensagem_id": m.id}, usuario_id, "painel")
    return m
