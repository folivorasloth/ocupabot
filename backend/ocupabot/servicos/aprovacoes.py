"""Humano no circuito: tudo o que o bot pede espera a equipe.

* NOVO / REMARCACAO: o agendamento pedido nasce em AGUARDANDO_APROVACAO e já segura a vaga.
* CANCELAMENTO: o agendamento continua valendo até a equipe decidir.
* Aprovar confere tudo de novo (data no futuro, vaga ainda livre, o agendamento de origem ainda vale).
  Recusar libera a vaga e passa a conversa para a equipe.
* Outro horário: a equipe não agenda por conta própria um horário que a pessoa não pediu. Ela PROPÕE:
  a vaga proposta fica segura, o pedido passa a AGUARDANDO_CLIENTE e a pessoa responde 1 (confirma) ou
  2 (outro horário). Só o 1 agenda, depois de conferir a vaga outra vez. A proposta vence no que vier
  primeiro entre `proposta_validade_horas` e 2 h antes do exame; vencida, a vaga é liberada e vira
  alerta no painel, sem mensagem automática.
* Nada acontece sozinho com a pessoa por demora da equipe: no máximo vira alerta no painel.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..dominio.datas import curta, hora
from ..dominio.texto import primeiro_nome
from ..enums import (
    AGENDA_PELA_EMPRESA,
    APROVACAO_EM_ABERTO,
    STATUS_ATIVOS,
    Autor,
    EstadoConversa,
    Perfil,
    StatusAgendamento,
    StatusAprovacao,
    TipoAprovacao,
)
from ..modelos import Agendamento, Aprovacao, Conversa
from ..relogio import agora
from . import agenda, auditoria, conversas, parametros, textos

ANTES_DO_EXAME = timedelta(hours=2)  # a proposta vence antes disso: a pessoa precisa de tempo para chegar
SUPERVISAO = (Perfil.SUPERVISAO, Perfil.ADMIN)

MARCADOR_RH = "RH não confirmado"
MARCADOR_CADASTRO = "nascimento diferente do cadastro"
MARCADOR_DUPLICADO = "já tem pedido pendente para este paciente"


class SemPermissao(Exception):
    pass


class PropostaEncerrada(agenda.OperacaoInvalida):
    """A proposta venceu ou já foi encerrada."""


def pedir(s: Session, tipo: TipoAprovacao, ag: Agendamento, original: Agendamento | None = None,
          contato_id: int | None = None, divergencia: bool = False) -> Aprovacao:
    ap = Aprovacao(tipo=tipo, agendamento_id=ag.id, original_id=original.id if original else None,
                   contato_id=contato_id or ag.contato_id, divergencia_cadastro=divergencia)
    s.add(ap)
    s.flush()
    auditoria.registrar(s, "aprovacao", ap.id, "pedir", depois=auditoria.foto(ap), ator="bot")
    return ap


def pendentes(s: Session) -> list[Aprovacao]:
    return list(s.scalars(select(Aprovacao).where(Aprovacao.status == StatusAprovacao.PENDENTE)
                          .order_by(Aprovacao.id)))


def marcadores(s: Session, ap: Aprovacao) -> list[str]:
    """O que a recepção precisa conferir antes de aprovar. Só avisam, não decidem nada."""
    saida = []
    ag, c = ap.agendamento, ap.contato
    if c is not None and ag.empresa_id is not None:
        if not (c.tipo in AGENDA_PELA_EMPRESA and ag.empresa_id in c.empresas_ids):
            saida.append(MARCADOR_RH)  # qualquer um que saiba o CNPJ chega até o pedido
    if ap.divergencia_cadastro:
        saida.append(MARCADOR_CADASTRO)
    outro = s.scalar(
        select(Aprovacao.id).join(Agendamento, Agendamento.id == Aprovacao.agendamento_id)
        .where(Agendamento.paciente_id == ag.paciente_id, Aprovacao.status.in_(APROVACAO_EM_ABERTO),
               Aprovacao.id != ap.id).limit(1)
    )
    if outro is not None:
        saida.append(MARCADOR_DUPLICADO)
    return saida


def exige_supervisao(ap: Aprovacao) -> bool:
    alvo = ap.original if ap.tipo == TipoAprovacao.REMARCACAO else ap.agendamento
    return ap.tipo != TipoAprovacao.NOVO and alvo is not None and alvo.no_sistema_externo


def _valores(ag: Agendamento) -> dict:
    return {"paciente": primeiro_nome(ag.paciente.nome), "data": curta(ag.data), "horario": hora(ag.horario)}


def _conversa(s: Session, ap: Aprovacao) -> Conversa | None:
    if not ap.contato_id:
        return None
    return s.scalar(select(Conversa).where(Conversa.contato_id == ap.contato_id))


def _avisar(s: Session, ap: Aprovacao, chave: str, ag: Agendamento | None, usuario_id: int | None) -> None:
    conv = _conversa(s, ap)
    if conv is not None:
        conversas.enfileirar(s, conv, textos.texto(s, chave, **(_valores(ag) if ag else {})), Autor.EQUIPE,
                             usuario_id)


def _para_a_equipe(s: Session, ap: Aprovacao, motivo: str, avisado: bool = False) -> None:
    conv = _conversa(s, ap)
    if conv is not None:
        conversas.passar_para_equipe(s, conv, motivo, avisado)


def _decidir(ap: Aprovacao, status: StatusAprovacao, usuario_id: int | None, motivo: str | None) -> None:
    ap.status = status
    ap.decidida_em = agora()
    ap.decidida_por_id = usuario_id
    ap.motivo = (motivo or None) and motivo[:300]


def _conferir(ap: Aprovacao, esperado: StatusAprovacao = StatusAprovacao.PENDENTE) -> None:
    if ap.status != esperado:
        raise agenda.OperacaoInvalida("pedido já decidido")


def _conferir_base(ap: Aprovacao) -> None:
    """O agendamento de origem ainda vale? Entre o pedido e a decisão a equipe pode ter mexido nele."""
    if ap.tipo == TipoAprovacao.CANCELAMENTO:
        ok = ap.agendamento.status in STATUS_ATIVOS
    elif ap.tipo == TipoAprovacao.REMARCACAO and ap.original is not None:
        ok = ap.original.status in STATUS_ATIVOS | {StatusAgendamento.FALTOU}
    else:
        ok = True
    if not ok:
        raise agenda.OperacaoInvalida("o agendamento mudou depois do pedido (cancelado, remarcado ou atendido): "
                                      "recuse o pedido")


def _conferir_vaga(s: Session, ag: Agendamento) -> None:
    """A vaga ainda existe? (ignora o próprio pedido, que já a segura)"""
    if agenda.agora_passou(ag):
        raise agenda.VagaIndisponivel("a data do pedido já passou; proponha outro horário")
    if ag.horario not in agenda.livres(s, ag.data, [i.exame_id for i in ag.itens], ignorar={ag.id}):
        raise agenda.VagaIndisponivel("o horário pedido não está mais livre; proponha outro horário")


def _efetivar(s: Session, ap: Aprovacao, usuario_id: int | None) -> Agendamento:
    ag = ap.agendamento
    ag.status = StatusAgendamento.AGENDADO
    agenda.programar_avisos(s, ag, confirmacao=False)
    if ap.tipo == TipoAprovacao.REMARCACAO and ap.original is not None:
        orig = ap.original
        if orig.status in STATUS_ATIVOS:
            orig.status = StatusAgendamento.REMARCADO
        agenda.cancelar_avisos(s, orig.id)
        ag.remarcado_de_id = orig.id
    _decidir(ap, StatusAprovacao.APROVADA, usuario_id, None)
    s.flush()
    return ag


def aprovar(s: Session, ap: Aprovacao, usuario_id: int, perfil: Perfil) -> Agendamento:
    _conferir(ap)
    if exige_supervisao(ap) and perfil not in SUPERVISAO:
        raise SemPermissao("mudar o que já está no sistema externo exige a Supervisão")
    _conferir_base(ap)
    antes = auditoria.foto(ap)
    ag = ap.agendamento
    if ap.tipo == TipoAprovacao.CANCELAMENTO:
        agenda.cancelar(s, ag, "Pedido pelo WhatsApp, aprovado pela equipe", usuario_id, "painel")
        _decidir(ap, StatusAprovacao.APROVADA, usuario_id, None)
        _avisar(s, ap, "cancelamento_confirmado", ag, usuario_id)
    else:
        _conferir_vaga(s, ag)
        _efetivar(s, ap, usuario_id)
        _avisar(s, ap, "agendado", ag, usuario_id)
    auditoria.registrar(s, "aprovacao", ap.id, "aprovar", antes, auditoria.foto(ap), usuario_id, "painel")
    return ag


# --- Proposta de outro horário ---------------------------------------------------------------------

def vence_em(s: Session, data: date, horario: time) -> datetime:
    prazo = agora() + timedelta(hours=parametros.inteiro(s, "proposta_validade_horas"))
    return min(prazo, datetime.combine(data, horario) - ANTES_DO_EXAME)


def propor(s: Session, ap: Aprovacao, usuario_id: int, perfil: Perfil, data: date, horario: time) -> Aprovacao:
    """Segura o horário proposto e pergunta à pessoa. NÃO agenda: isso só acontece quando ela responde 1."""
    _conferir(ap)
    if ap.tipo == TipoAprovacao.CANCELAMENTO:
        raise agenda.OperacaoInvalida("cancelamento não tem horário para propor: aprove ou recuse")
    _conferir_base(ap)
    if exige_supervisao(ap) and perfil not in SUPERVISAO:
        raise SemPermissao("este agendamento está no sistema externo: só a Supervisão propõe outro horário")
    if ap.contato is None:
        raise agenda.OperacaoInvalida("pedido sem contato de WhatsApp: recuse e combine o horário por telefone")
    if ap.contato.optout_em is not None:
        raise agenda.OperacaoInvalida("esta pessoa pediu SAIR: a proposta não chegaria. Recuse e combine o "
                                      "horário por telefone")
    pedido = ap.agendamento
    if (data, horario) == (pedido.data, pedido.horario):
        raise agenda.OperacaoInvalida("esse é o horário que a pessoa pediu: aprove o pedido")
    ate = vence_em(s, data, horario)
    if ate <= agora():
        raise agenda.OperacaoInvalida("faltam menos de 2 h para esse horário: a pessoa não teria tempo de "
                                      "responder. Proponha outro")
    antes = auditoria.foto(ap)
    novo = agenda.criar(
        s, paciente_id=pedido.paciente_id, exame_ids=[i.exame_id for i in pedido.itens], data=data,
        horario=horario, origem=pedido.origem, status=StatusAgendamento.AGUARDANDO_APROVACAO,
        empresa_id=pedido.empresa_id, contato_id=pedido.contato_id, tipo_aso_id=pedido.tipo_aso_id,
        observacao=pedido.observacao, usuario_id=usuario_id, ator="painel", ignorar={pedido.id},
    )
    pedido.status = StatusAgendamento.CANCELADO
    pedido.motivo_cancelamento = "Outro horário proposto pela equipe"
    ap.agendamento = novo
    ap.alterada = True
    ap.status = StatusAprovacao.AGUARDANDO_CLIENTE
    ap.proposta_em, ap.proposta_ate, ap.proposta_por_id = agora(), ate, usuario_id
    conv = conversas.conversa_de(s, ap.contato)
    conversas.enfileirar(s, conv, textos.texto(s, "proposta_horario", **_valores(novo)), Autor.EQUIPE, usuario_id)
    # a resposta (1 ou 2) volta para o bot
    conv.estado, conv.fluxo, conv.etapa = EstadoConversa.BOT, "PROPOSTA", "RESPOSTA"
    conv.dados = {"proposta": ap.id, "_dica": "Responda 1 para confirmar ou 2 para outro horário."}
    conv.atendente_id, conv.motivo_humano, conv.erros_seguidos = None, None, 0
    s.flush()
    auditoria.registrar(s, "aprovacao", ap.id, "propor", antes, auditoria.foto(ap), usuario_id, "painel")
    return ap


def venceu(ap: Aprovacao) -> bool:
    return ap.proposta_ate is not None and agora() > ap.proposta_ate


def confirmar_proposta(s: Session, ap: Aprovacao) -> Agendamento:
    """A pessoa respondeu 1: confere a vaga de novo e agenda (decidida por quem propôs).
    PropostaEncerrada: venceu ou foi encerrada. VagaIndisponivel: o horário deixou de valer."""
    if ap.status != StatusAprovacao.AGUARDANDO_CLIENTE or venceu(ap):
        raise PropostaEncerrada("esta proposta já venceu ou foi encerrada")
    _conferir_base(ap)
    _conferir_vaga(s, ap.agendamento)
    antes = auditoria.foto(ap)
    ag = _efetivar(s, ap, ap.proposta_por_id)
    auditoria.registrar(s, "aprovacao", ap.id, "confirmar_proposta", antes, auditoria.foto(ap), ator="bot")
    return ag


def encerrar_proposta(s: Session, ap: Aprovacao, motivo: str, status: StatusAprovacao = StatusAprovacao.RECUSADA,
                      usuario_id: int | None = None, ator: str = "bot") -> None:
    """Libera a vaga proposta: a pessoa respondeu 2, o horário deixou de valer, a equipe desistiu ou venceu."""
    if ap.status != StatusAprovacao.AGUARDANDO_CLIENTE:
        raise PropostaEncerrada("esta proposta já foi encerrada")
    antes = auditoria.foto(ap)
    ag = ap.agendamento
    if ag.status == StatusAgendamento.AGUARDANDO_APROVACAO:
        ag.status = StatusAgendamento.CANCELADO
        ag.motivo_cancelamento = f"Proposta não confirmada: {motivo}"[:200]
    _decidir(ap, status, usuario_id, motivo)
    auditoria.registrar(s, "aprovacao", ap.id, "encerrar_proposta", antes, auditoria.foto(ap), usuario_id, ator)


def cancelar_proposta(s: Session, ap: Aprovacao, usuario_id: int) -> None:
    """A equipe desiste da proposta: a vaga é liberada e a conversa volta para a equipe."""
    encerrar_proposta(s, ap, "proposta cancelada pela equipe", usuario_id=usuario_id, ator="painel")
    _para_a_equipe(s, ap, "proposta de horário cancelada pela equipe")


def expirar_propostas(s: Session) -> int:
    """Worker: proposta sem resposta no prazo libera a vaga e passa a conversa para a equipe, sem mensagem."""
    vencidas = s.scalars(select(Aprovacao).where(Aprovacao.status == StatusAprovacao.AGUARDANDO_CLIENTE,
                                                 Aprovacao.proposta_ate < agora())).all()
    for ap in vencidas:
        encerrar_proposta(s, ap, "a pessoa não respondeu a tempo", StatusAprovacao.EXPIRADA, ator="sistema")
        _para_a_equipe(s, ap, "proposta de horário venceu sem resposta")
    return len(vencidas)


def recusar(s: Session, ap: Aprovacao, usuario_id: int, motivo: str | None = None) -> None:
    _conferir(ap)
    antes = auditoria.foto(ap)
    if ap.tipo in (TipoAprovacao.NOVO, TipoAprovacao.REMARCACAO):
        ag = ap.agendamento
        ag.status = StatusAgendamento.CANCELADO
        ag.motivo_cancelamento = f"Pedido recusado: {motivo or 'sem motivo informado'}"[:200]
    _decidir(ap, StatusAprovacao.RECUSADA, usuario_id, motivo)
    _avisar(s, ap, "aprovacao_recusada", None, usuario_id)
    _para_a_equipe(s, ap, f"pedido recusado: {motivo or 'sem motivo informado'}", avisado=True)
    auditoria.registrar(s, "aprovacao", ap.id, "recusar", antes, auditoria.foto(ap), usuario_id, "painel")
