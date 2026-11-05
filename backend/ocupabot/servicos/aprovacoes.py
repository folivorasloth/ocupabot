"""Humano no circuito: tudo o que o bot pede espera a equipe.

* NOVO / REMARCACAO: o agendamento pedido nasce em AGUARDANDO_APROVACAO e já segura a vaga.
* CANCELAMENTO: o agendamento continua valendo até a equipe decidir.
* Aprovar confere tudo de novo (data no futuro, vaga ainda livre). Recusar libera a vaga e passa a
  conversa para a equipe. Nada acontece sozinho por demora: no máximo vira alerta no painel.
"""

from __future__ import annotations

from datetime import date, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..dominio.datas import curta, hora
from ..dominio.texto import primeiro_nome
from ..enums import (
    Autor,
    Origem,
    Perfil,
    StatusAgendamento,
    StatusAprovacao,
    TipoAprovacao,
)
from ..modelos import Agendamento, Aprovacao, Conversa
from ..relogio import agora
from . import agenda, auditoria, conversas, textos


class SemPermissao(Exception):
    pass


def pedir(s: Session, tipo: TipoAprovacao, ag: Agendamento, original: Agendamento | None = None,
          contato_id: int | None = None) -> Aprovacao:
    ap = Aprovacao(tipo=tipo, agendamento_id=ag.id, original_id=original.id if original else None,
                   contato_id=contato_id or ag.contato_id)
    s.add(ap)
    s.flush()
    auditoria.registrar(s, "aprovacao", ap.id, "pedir", depois=auditoria.foto(ap), ator="bot")
    return ap


def pendentes(s: Session) -> list[Aprovacao]:
    return list(s.scalars(select(Aprovacao).where(Aprovacao.status == StatusAprovacao.PENDENTE)
                          .order_by(Aprovacao.id)))


def _exige_supervisao(ap: Aprovacao) -> bool:
    alvo = ap.original if ap.tipo == TipoAprovacao.REMARCACAO else ap.agendamento
    return ap.tipo != TipoAprovacao.NOVO and alvo is not None and alvo.no_sistema_externo


def _avisar(s: Session, ap: Aprovacao, chave: str, ag: Agendamento | None, usuario_id: int) -> None:
    if not ap.contato_id:
        return
    conv = s.scalar(select(Conversa).where(Conversa.contato_id == ap.contato_id))
    if conv is None:
        return
    valores = {}
    if ag is not None:
        valores = {"paciente": primeiro_nome(ag.paciente.nome), "data": curta(ag.data),
                   "horario": hora(ag.horario)}
    conversas.enfileirar(s, conv, textos.texto(s, chave, **valores), Autor.EQUIPE, usuario_id)


def _decidir(ap: Aprovacao, status: StatusAprovacao, usuario_id: int, motivo: str | None) -> None:
    ap.status = status
    ap.decidida_em = agora()
    ap.decidida_por_id = usuario_id
    ap.motivo = (motivo or None) and motivo[:300]


def aprovar(s: Session, ap: Aprovacao, usuario_id: int, perfil: Perfil,
            nova_data: date | None = None, novo_horario: time | None = None) -> Agendamento:
    if ap.status != StatusAprovacao.PENDENTE:
        raise agenda.OperacaoInvalida("pedido já decidido")
    if _exige_supervisao(ap) and perfil not in (Perfil.SUPERVISAO, Perfil.ADMIN):
        raise SemPermissao("mudar o que já está no sistema externo exige a Supervisão")
    antes = auditoria.foto(ap)
    ag = ap.agendamento

    if ap.tipo == TipoAprovacao.CANCELAMENTO:
        agenda.cancelar(s, ag, "Pedido pelo WhatsApp, aprovado pela equipe", usuario_id, "painel")
        _decidir(ap, StatusAprovacao.APROVADA, usuario_id, None)
        _avisar(s, ap, "cancelamento_confirmado", ag, usuario_id)
        auditoria.registrar(s, "aprovacao", ap.id, "aprovar", antes, auditoria.foto(ap), usuario_id, "painel")
        return ag

    alterou = (nova_data and nova_data != ag.data) or (novo_horario and novo_horario != ag.horario)
    if alterou:
        final = agenda.criar(
            s, paciente_id=ag.paciente_id, exame_ids=[i.exame_id for i in ag.itens],
            data=nova_data or ag.data, horario=novo_horario or ag.horario, origem=Origem.WHATSAPP,
            empresa_id=ag.empresa_id, contato_id=ag.contato_id, tipo_aso_id=ag.tipo_aso_id,
            observacao=ag.observacao, usuario_id=usuario_id, ator="painel", ignorar={ag.id},
            avisar_confirmacao=False,
        )
        final.remarcado_de_id = ag.remarcado_de_id
        ag.status = StatusAgendamento.CANCELADO
        ag.motivo_cancelamento = "Horário alterado pela equipe na aprovação"
        ap.alterada = True
    else:
        # confere de novo: a vaga ainda existe? (ignora o próprio pedido, que já a segura)
        if agenda.agora_passou(ag):
            raise agenda.VagaIndisponivel("a data do pedido já passou; altere o horário")
        livres = agenda.livres(s, ag.data, [i.exame_id for i in ag.itens], ignorar={ag.id})
        if ag.horario not in livres:
            raise agenda.VagaIndisponivel("o horário pedido não está mais livre; altere o horário")
        final = ag
        final.status = StatusAgendamento.AGENDADO
        agenda.programar_avisos(s, final, confirmacao=False)

    if ap.tipo == TipoAprovacao.REMARCACAO and ap.original is not None:
        orig = ap.original
        if orig.status in (StatusAgendamento.AGENDADO, StatusAgendamento.CONFIRMADO):
            orig.status = StatusAgendamento.REMARCADO
        agenda.cancelar_avisos(s, orig.id)
        final.remarcado_de_id = orig.id

    _decidir(ap, StatusAprovacao.APROVADA, usuario_id, None)
    s.flush()
    _avisar(s, ap, "agendado", final, usuario_id)
    auditoria.registrar(s, "aprovacao", ap.id, "aprovar", antes,
                        {**auditoria.foto(ap), "agendamento_final": final.id}, usuario_id, "painel")
    return final


def recusar(s: Session, ap: Aprovacao, usuario_id: int, motivo: str) -> None:
    if ap.status != StatusAprovacao.PENDENTE:
        raise agenda.OperacaoInvalida("pedido já decidido")
    antes = auditoria.foto(ap)
    if ap.tipo in (TipoAprovacao.NOVO, TipoAprovacao.REMARCACAO):
        ag = ap.agendamento
        ag.status = StatusAgendamento.CANCELADO
        ag.motivo_cancelamento = f"Pedido recusado: {motivo}"[:200]
    _decidir(ap, StatusAprovacao.RECUSADA, usuario_id, motivo)
    _avisar(s, ap, "aprovacao_recusada", None, usuario_id)
    if ap.contato_id:
        conv = s.scalar(select(Conversa).where(Conversa.contato_id == ap.contato_id))
        if conv is not None:
            conversas.passar_para_equipe(s, conv, f"pedido recusado: {motivo}")
    auditoria.registrar(s, "aprovacao", ap.id, "recusar", antes, auditoria.foto(ap), usuario_id, "painel")
