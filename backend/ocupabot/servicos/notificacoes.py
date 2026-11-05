"""Avisos automáticos (confirmação, lembrete, falta, remarcação).

Só saem com o parâmetro `envios_automaticos` ligado. Viram mensagens na conversa do contato e
seguem pela mesma fila de saída das demais mensagens.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..dominio.datas import curta, hora
from ..dominio.texto import primeiro_nome
from ..enums import STATUS_ATIVOS, Autor, StatusAgendamento, StatusNotificacao, TipoNotificacao
from ..modelos import Notificacao
from ..relogio import agora
from . import conversas, parametros, textos

CHAVE = {
    TipoNotificacao.CONFIRMACAO: "confirmacao",
    TipoNotificacao.LEMBRETE_D1: "lembrete_d1",
    TipoNotificacao.FALTA: "aviso_falta",
    TipoNotificacao.REMARCAR: "aviso_remarcar",
}
# Tipos que esperam resposta da pessoa
COM_RESPOSTA = {TipoNotificacao.LEMBRETE_D1, TipoNotificacao.FALTA, TipoNotificacao.REMARCAR}


def _ainda_vale(n: Notificacao) -> bool:
    ag = n.agendamento
    if ag is None:
        return True
    if n.tipo == TipoNotificacao.FALTA:
        return ag.status == StatusAgendamento.FALTOU
    if n.tipo == TipoNotificacao.LEMBRETE_D1:
        return ag.status in STATUS_ATIVOS and ag.data > n.enviar_em.date()
    return ag.status in STATUS_ATIVOS


def processar(s: Session, limite: int = 50) -> int:
    if not parametros.ligado(s, "envios_automaticos"):
        return 0
    vencidas = s.scalars(
        select(Notificacao).where(Notificacao.status == StatusNotificacao.AGENDADA,
                                  Notificacao.enviar_em <= agora()).order_by(Notificacao.enviar_em).limit(limite)
    ).all()
    for n in vencidas:
        if n.contato.optout_em is not None:
            n.status, n.erro = StatusNotificacao.CANCELADA, "contato pediu para sair"
            continue
        if not _ainda_vale(n):
            n.status, n.erro = StatusNotificacao.CANCELADA, "agendamento mudou"
            continue
        ag = n.agendamento
        valores = {}
        if ag is not None:
            valores = {"paciente": primeiro_nome(ag.paciente.nome), "data": curta(ag.data),
                       "horario": hora(ag.horario)}
        conv = conversas.conversa_de(s, n.contato)
        conversas.enfileirar(s, conv, textos.texto(s, CHAVE[n.tipo], **valores), Autor.SISTEMA)
        n.status = StatusNotificacao.ENVIADA
        n.enviada_em = agora()
    return len(vencidas)


def aguardando_resposta(s: Session, contato_id: int) -> list[Notificacao]:
    """Avisos enviados nas últimas 48 h que ainda esperam resposta."""
    desde = agora() - timedelta(hours=48)
    return list(s.scalars(
        select(Notificacao).where(Notificacao.contato_id == contato_id,
                                  Notificacao.status == StatusNotificacao.ENVIADA,
                                  Notificacao.tipo.in_(COM_RESPOSTA),
                                  Notificacao.enviada_em >= desde).order_by(Notificacao.enviada_em.desc())
    ))
