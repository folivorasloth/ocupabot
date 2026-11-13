"""Mensagens seguidas do mesmo número viram UMA resposta.

Quem escreve em várias mensagens ("oi" / "bom dia" / "quero agendar") recebia uma resposta para cada uma.
Agora:

1. o webhook só GRAVA a mensagem em `entradas_pendentes` (não responde);
2. a cada segundo, o laço do app (`responder_vencidas`) procura os números cuja última mensagem pendente
   tem mais de `agrupar_mensagens_segundos`. Mensagem nova do mesmo número dentro da janela adia, porque
   a conta é pela ÚLTIMA. Rajada que não para recebe resposta depois de no máximo ESPERA_MAXIMA segundos;
3. as mensagens passam, em ordem, pela máquina de estados de sempre, cada uma num SAVEPOINT; sai só a
   resposta final;
4. mensagem que não fez a conversa andar ("não entendi", repetição do menu) depois de uma que respondeu
   algo na mesma rajada é desfeita e fica só no histórico: "Admissional" + "obrigado" manda a pergunta do
   próximo passo, não "não entendi".

Fica no banco, não em memória: reiniciar o app no meio da janela não perde mensagem.
`agrupar_mensagens_segundos` = 0 volta a responder cada mensagem na hora, no próprio webhook.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import db
from ..enums import Autor, EstadoConversa
from ..integracoes.mensageria import canal
from ..modelos import EntradaPendente
from ..relogio import agora
from ..servicos import conversas, parametros, textos
from . import maquina

log = logging.getLogger("ocupabot.rajadas")

ESPERA_MAXIMA = 60  # segundos: quem não para de escrever recebe resposta mesmo assim


def janela(s: Session) -> int:
    return parametros.inteiro(s, "agrupar_mensagens_segundos")


def guardar(s: Session, telefone: str, texto: str, id_externo: str | None) -> bool:
    """Webhook: guarda a mensagem para a próxima rodada. False se for repetida (mesmo id)."""
    if conversas.ja_recebida(s, id_externo):
        return False
    s.add(EntradaPendente(telefone=telefone, texto=texto[:4000], id_externo=id_externo, recebida_em=agora()))
    return True


def responder(s: Session, telefone: str, entradas: list[tuple[str, str | None]]) -> list[str]:
    """As mensagens, em ordem, pela máquina de estados; enfileira e devolve só a resposta final."""
    final: list[str] = []
    conv = None
    midia_sem_resposta = False
    for texto, id_externo in entradas:
        ponto = s.begin_nested()
        bot = maquina.atender(s, telefone, texto, id_externo, gravar_saida=False)
        if bot is None:  # repetida
            ponto.commit()
            continue
        if final and bot.sem_avanco:  # não troca a resposta que já vale por "não entendi"
            ponto.rollback()
            conv = conversas.conversa_de(s, conversas.contato(s, telefone))
            maquina.registrar(s, conv, texto.strip(), id_externo)  # mas a mensagem fica no histórico
            midia_sem_resposta = midia_sem_resposta or texto == conversas.MIDIA
            continue
        ponto.commit()
        conv = bot.conv
        if bot.saida:
            final = list(bot.saida)
    if conv is None:
        return []
    if midia_sem_resposta and conv.estado == EstadoConversa.BOT:
        aviso = textos.texto(s, "midia_nao_suportada")  # o áudio do meio da rajada não foi ouvido
        if aviso not in final:
            final.append(aviso)
    for r in final:
        conversas.enfileirar(s, conv, r, Autor.BOT)
    return final


def _pendentes(s: Session, telefone: str) -> list[EntradaPendente]:
    return list(s.scalars(select(EntradaPendente).where(EntradaPendente.telefone == telefone)
                          .order_by(EntradaPendente.recebida_em, EntradaPendente.id)))


def _um_numero(telefone: str) -> None:
    with db.sessao() as s:
        pendentes = _pendentes(s, telefone)
        entradas = [(p.texto, p.id_externo) for p in pendentes]
        for p in pendentes:
            s.delete(p)  # somem na mesma transação em que a resposta é gravada
        s.flush()
        responder(s, telefone, entradas)


def _sem_bot(telefone: str) -> None:
    """Erro ao processar a rajada: as mensagens não se perdem; ficam no histórico e a conversa vai à equipe."""
    try:
        with db.sessao() as s:
            conv = conversas.conversa_de(s, conversas.contato(s, telefone))
            for p in _pendentes(s, telefone):
                maquina.registrar(s, conv, p.texto, p.id_externo)
                s.delete(p)
            conversas.passar_para_equipe(s, conv, "erro ao processar as mensagens")
    except Exception as e:  # noqa: BLE001
        log.error("rajada sem bot falhou: %s", type(e).__name__)


def responder_vencidas(enviar: bool = True) -> int:
    """Uma passada: responde as rajadas que terminaram. Devolve quantos números responderam."""
    with db.sessao() as s:
        segundos = janela(s)
        grupos = s.execute(select(EntradaPendente.telefone, func.max(EntradaPendente.recebida_em),
                                  func.min(EntradaPendente.recebida_em)).group_by(EntradaPendente.telefone)).all()
    calado = agora() - timedelta(seconds=segundos)
    teto = agora() - timedelta(seconds=max(ESPERA_MAXIMA, segundos))
    feitos = 0
    for telefone, ultima, primeira in grupos:
        if not (ultima <= calado or primeira <= teto):
            continue
        try:
            _um_numero(telefone)
            feitos += 1
        except Exception as e:  # noqa: BLE001 - um número com problema não trava os outros
            log.error("rajada falhou: %s", type(e).__name__)  # sem telefone nem texto no log
            _sem_bot(telefone)
    if feitos and enviar:
        try:  # tenta enviar já; o que falhar o worker reenvia dentro da validade
            with db.sessao() as s:
                conversas.enviar_pendentes(s, canal(), limite=30)
        except Exception:  # noqa: BLE001
            log.exception("envio das respostas falhou")
    return feitos
