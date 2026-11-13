"""Agenda: vagas, criar, remarcar, cancelar, presença e falta."""

from __future__ import annotations

import hashlib
from datetime import date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..config import config
from ..dominio.vagas import Indisponibilidade, Ocupacao, Retrato
from ..enums import STATUS_OCUPAM, Origem, StatusAgendamento, StatusNotificacao, TipoNotificacao, Turno
from ..modelos import (
    Agendamento,
    Contato,
    Exame,
    Excecao,
    Expediente,
    Funcao,
    Grade,
    ItemAgendamento,
    LeituraExterna,
    Notificacao,
    OcupacaoExterna,
    Profissional,
)
from ..relogio import agora, hoje
from . import auditoria, parametros


class VagaIndisponivel(Exception):
    pass


class OperacaoInvalida(Exception):
    pass


# --- Retrato para o motor de vagas -----------------------------------------------------------------

def carregar_retrato(s: Session, de: date, ate: date, ignorar: set[int] | None = None) -> Retrato:
    ignorar = ignorar or set()
    expediente = {(e.dia_semana, e.turno.value): (e.inicio, e.fim) for e in s.scalars(select(Expediente))}
    grade: dict[tuple[int, str, int], set[int]] = {}
    consulta = (
        select(Grade)
        .join(Profissional, Profissional.id == Grade.profissional_id)
        .join(Funcao, Funcao.id == Grade.funcao_id)
        .where(Grade.confirmada.is_(True), Profissional.ativo.is_(True), Funcao.ativa.is_(True))
    )
    for g in s.scalars(consulta):
        grade.setdefault((g.dia_semana, g.turno.value, g.funcao_id), set()).add(g.profissional_id)
    padrao = parametros.inteiro(s, "capacidade_padrao_por_hora")
    capacidade = {f.id: f.capacidade_por_hora or padrao for f in s.scalars(select(Funcao))}
    excecoes = [
        Indisponibilidade(e.profissional_id, e.data_inicio, e.data_fim, e.turno.value if e.turno else None)
        for e in s.scalars(select(Excecao).where(Excecao.data_fim >= de, Excecao.data_inicio <= ate))
    ]
    ocupacoes = []
    linhas = s.execute(
        select(Agendamento.id, Agendamento.data, Agendamento.horario, Exame.funcao_id,
               ItemAgendamento.profissional_id)
        .join(ItemAgendamento, ItemAgendamento.agendamento_id == Agendamento.id)
        .join(Exame, Exame.id == ItemAgendamento.exame_id)
        .where(Agendamento.data.between(de, ate), Agendamento.status.in_(STATUS_OCUPAM))
    )
    for ag_id, d, h, funcao_id, prof_id in linhas:
        if ag_id not in ignorar and funcao_id is not None:
            ocupacoes.append(Ocupacao(d, h, funcao_id, prof_id))
    bloqueios = {
        (o.data, o.horario)
        for o in s.scalars(select(OcupacaoExterna).where(OcupacaoExterna.data.between(de, ate)))
    }
    return Retrato(expediente=expediente, grade=grade, capacidade=capacidade,
                   passo_min=parametros.inteiro(s, "passo_min"), excecoes=excecoes,
                   ocupacoes=ocupacoes, bloqueios=bloqueios)


def funcoes_dos_exames(s: Session, exame_ids: list[int]) -> list[int]:
    exames = s.scalars(select(Exame).where(Exame.id.in_(exame_ids))).all()
    if len(exames) != len(set(exame_ids)):
        raise OperacaoInvalida("exame inexistente")
    return sorted({e.funcao_id for e in exames if e.funcao_id is not None})


def exames_de_especialista(s: Session, exame_ids: list[int]) -> list[Exame]:
    return list(
        s.scalars(select(Exame).join(Funcao).where(Exame.id.in_(exame_ids), Funcao.requer_humano.is_(True)))
    )


def _nao_antes(s: Session, para_bot: bool) -> datetime:
    """O bot não oferece horário em cima da hora; a equipe pode marcar pelo painel."""
    minutos = parametros.inteiro(s, "antecedencia_minima_min") if para_bot else 0
    return agora() + timedelta(minutes=minutos)


def livres(s: Session, d: date, exame_ids: list[int], para_bot: bool = False,
           ignorar: set[int] | None = None) -> list[time]:
    funcoes = funcoes_dos_exames(s, exame_ids)
    r = carregar_retrato(s, d, d, ignorar)
    bloquear = para_bot and parametros.ligado(s, "bloquear_horario_externo")
    return r.livres_no_dia(d, funcoes, nao_antes=_nao_antes(s, para_bot), bloquear_externos=bloquear)


def proximos_dias(s: Session, exame_ids: list[int], quantos: int, para_bot: bool = True,
                  a_partir: date | None = None) -> list[tuple[date, list[time]]]:
    """Os próximos `quantos` dias com vaga, dentro do prazo máximo."""
    inicio = a_partir or hoje()
    fim = hoje() + timedelta(days=parametros.inteiro(s, "prazo_maximo_dias"))
    if inicio > fim:
        return []
    funcoes = funcoes_dos_exames(s, exame_ids)
    r = carregar_retrato(s, inicio, fim)
    bloquear = para_bot and parametros.ligado(s, "bloquear_horario_externo")
    saida = []
    d = inicio
    while d <= fim and len(saida) < quantos:
        hs = r.livres_no_dia(d, funcoes, nao_antes=_nao_antes(s, para_bot), bloquear_externos=bloquear)
        if hs:
            saida.append((d, hs))
        d += timedelta(days=1)
    return saida


def dentro_do_prazo(s: Session, d: date) -> bool:
    return hoje() <= d <= hoje() + timedelta(days=parametros.inteiro(s, "prazo_maximo_dias"))


def conferir_teto(s: Session, d: date) -> None:
    """A equipe não agenda, remarca nem propõe além de `agenda_max_dias_futuro` (data digitada errada)."""
    dias = parametros.inteiro(s, "agenda_max_dias_futuro")
    if d > hoje() + timedelta(days=dias):
        raise OperacaoInvalida(f"data longe demais: o limite é de {dias} dias à frente")


# --- Sistema externo -------------------------------------------------------------------------------

def integracao_externa_ativa() -> bool:
    return config().agenda_externa not in ("", "nenhum")


def leitura_externa_valida(s: Session) -> bool:
    if not integracao_externa_ativa() or not parametros.ligado(s, "exige_leitura_externa"):
        return True
    ultima = s.scalars(select(LeituraExterna).order_by(LeituraExterna.id.desc()).limit(1)).first()
    if ultima is None or not ultima.ok or ultima.concluida_em is None:
        return False
    validade = timedelta(minutes=parametros.inteiro(s, "leitura_externa_validade_min"))
    return agora() - ultima.concluida_em <= validade


def hash_cpf(cpf: str) -> str:
    return hashlib.sha256((config().segredo + ":" + cpf).encode()).hexdigest()


def paciente_ocupado_externo(s: Session, cpf: str | None) -> bool:
    if not cpf:
        return False
    return s.scalar(
        select(OcupacaoExterna.id).where(OcupacaoExterna.cpf_hash == hash_cpf(cpf),
                                         OcupacaoExterna.data >= hoje()).limit(1)
    ) is not None


# --- Escrita ---------------------------------------------------------------------------------------

def _turno(r: Retrato, d: date, t: time) -> str:
    turno = r.turno_de(d, t)
    if turno is None:
        raise VagaIndisponivel("fora do expediente")
    return turno


def criar(
    s: Session,
    *,
    paciente_id: int,
    exame_ids: list[int],
    data: date,
    horario: time,
    origem: Origem,
    status: StatusAgendamento = StatusAgendamento.AGENDADO,
    empresa_id: int | None = None,
    contato_id: int | None = None,
    tipo_aso_id: int | None = None,
    observacao: str | None = None,
    para_bot: bool = False,
    forcar: bool = False,
    usuario_id: int | None = None,
    ator: str = "sistema",
    ignorar: set[int] | None = None,
    avisar_confirmacao: bool = True,
) -> Agendamento:
    """Cria conferindo a vaga dentro da mesma transação (BEGIN IMMEDIATE no SQLite)."""
    if not exame_ids:
        raise OperacaoInvalida("informe ao menos um exame")
    if datetime.combine(data, horario) <= agora() and not forcar:
        raise VagaIndisponivel("horário no passado")
    conferir_teto(s, data)
    if para_bot and datetime.combine(data, horario) <= _nao_antes(s, True):
        raise VagaIndisponivel("horário em cima da hora")
    funcoes = funcoes_dos_exames(s, exame_ids)
    r = carregar_retrato(s, data, data, ignorar)
    bloquear = para_bot and parametros.ligado(s, "bloquear_horario_externo")
    escolha = r.atribuir(data, horario, funcoes, bloquear_externos=bloquear)
    if escolha is None and not forcar:
        raise VagaIndisponivel(f"{data:%d/%m} {horario:%H:%M} não está livre")
    escolha = escolha or {}
    turno = r.turno_de(data, horario) or ("MANHA" if horario < time(12) else "TARDE")
    ag = Agendamento(paciente_id=paciente_id, empresa_id=empresa_id, contato_id=contato_id,
                     tipo_aso_id=tipo_aso_id, data=data, horario=horario, turno=Turno(turno), status=status,
                     origem=origem, observacao=observacao)
    exames = s.scalars(select(Exame).where(Exame.id.in_(exame_ids))).all()
    ag.itens = [ItemAgendamento(exame_id=e.id, profissional_id=escolha.get(e.funcao_id)) for e in exames]
    s.add(ag)
    s.flush()
    auditoria.registrar(s, "agendamento", ag.id, "criar", depois=auditoria.foto(ag),
                        usuario_id=usuario_id, ator=ator)
    if status in (StatusAgendamento.AGENDADO, StatusAgendamento.CONFIRMADO):
        programar_avisos(s, ag, confirmacao=avisar_confirmacao)
    return ag


def carregar(s: Session, ag_id: int) -> Agendamento:
    ag = s.get(Agendamento, ag_id, options=[selectinload(Agendamento.itens)])
    if ag is None:
        raise OperacaoInvalida("agendamento não encontrado")
    return ag


def _mudar_status(s: Session, ag: Agendamento, novo: StatusAgendamento, acao: str,
                  usuario_id: int | None, ator: str, motivo: str | None = None) -> None:
    antes = auditoria.foto(ag)
    ag.status = novo
    if motivo:
        ag.motivo_cancelamento = motivo[:200]
    s.flush()
    auditoria.registrar(s, "agendamento", ag.id, acao, antes, auditoria.foto(ag), usuario_id, ator)


def cancelar(s: Session, ag: Agendamento, motivo: str, usuario_id: int | None = None,
             ator: str = "sistema") -> None:
    if ag.status not in STATUS_OCUPAM or ag.status == StatusAgendamento.COMPARECEU:
        raise OperacaoInvalida("só é possível cancelar agendamento ativo")
    _mudar_status(s, ag, StatusAgendamento.CANCELADO, "cancelar", usuario_id, ator, motivo)
    cancelar_avisos(s, ag.id)


def _so_a_partir_do_dia(ag: Agendamento, o_que: str) -> None:
    if ag.data > hoje():
        raise OperacaoInvalida(f"{o_que} só pode ser marcada a partir do dia do exame")


def presenca(s: Session, ag: Agendamento, usuario_id: int | None = None, ator: str = "sistema") -> None:
    if ag.status not in (StatusAgendamento.AGENDADO, StatusAgendamento.CONFIRMADO, StatusAgendamento.FALTOU):
        raise OperacaoInvalida("status não permite marcar presença")
    _so_a_partir_do_dia(ag, "presença")
    _mudar_status(s, ag, StatusAgendamento.COMPARECEU, "presenca", usuario_id, ator)
    cancelar_avisos(s, ag.id)


def falta(s: Session, ag: Agendamento, usuario_id: int | None = None, ator: str = "sistema") -> None:
    if ag.status not in (StatusAgendamento.AGENDADO, StatusAgendamento.CONFIRMADO):
        raise OperacaoInvalida("status não permite marcar falta")
    _so_a_partir_do_dia(ag, "falta")
    _mudar_status(s, ag, StatusAgendamento.FALTOU, "falta", usuario_id, ator)
    cancelar_avisos(s, ag.id)
    if ag.contato_id:
        s.add(Notificacao(tipo=TipoNotificacao.FALTA, contato_id=ag.contato_id, agendamento_id=ag.id,
                          enviar_em=agora()))


def remarcar(s: Session, ag: Agendamento, data: date, horario: time, usuario_id: int | None = None,
             ator: str = "sistema", origem: Origem = Origem.PAINEL) -> Agendamento:
    if ag.status not in (StatusAgendamento.AGENDADO, StatusAgendamento.CONFIRMADO,
                         StatusAgendamento.FALTOU, StatusAgendamento.AGUARDANDO_APROVACAO):
        raise OperacaoInvalida("status não permite remarcar")
    novo = criar(s, paciente_id=ag.paciente_id, exame_ids=[i.exame_id for i in ag.itens], data=data,
                 horario=horario, origem=origem, empresa_id=ag.empresa_id, contato_id=ag.contato_id,
                 tipo_aso_id=ag.tipo_aso_id, observacao=ag.observacao, usuario_id=usuario_id, ator=ator,
                 ignorar={ag.id})
    novo.remarcado_de_id = ag.id
    if ag.status != StatusAgendamento.FALTOU:
        _mudar_status(s, ag, StatusAgendamento.REMARCADO, "remarcar", usuario_id, ator)
    cancelar_avisos(s, ag.id)
    return novo


# --- Avisos ----------------------------------------------------------------------------------------

def programar_avisos(s: Session, ag: Agendamento, confirmacao: bool = True) -> None:
    if not ag.contato_id:
        return
    if confirmacao:
        s.add(Notificacao(tipo=TipoNotificacao.CONFIRMACAO, contato_id=ag.contato_id,
                          agendamento_id=ag.id, enviar_em=agora()))
    quando = datetime.combine(ag.data - timedelta(days=1), parametros.hora(s, "lembrete_hora"))
    if quando <= agora():
        # marcou para amanhã depois da hora do lembrete: sai logo, se ainda não for tarde da noite
        vespera = ag.data - timedelta(days=1) == hoje()
        if not (vespera and agora().time() < parametros.hora(s, "lembrete_limite_hora")):
            return
        quando = agora()
    s.add(Notificacao(tipo=TipoNotificacao.LEMBRETE_D1, contato_id=ag.contato_id,
                      agendamento_id=ag.id, enviar_em=quando))


def cancelar_avisos(s: Session, ag_id: int) -> None:
    for n in s.scalars(select(Notificacao).where(Notificacao.agendamento_id == ag_id,
                                                  Notificacao.status == StatusNotificacao.AGENDADA)):
        n.status = StatusNotificacao.CANCELADA


def afetados_por_excecao(s: Session, ex: Excecao) -> list[Agendamento]:
    consulta = (
        select(Agendamento)
        .where(Agendamento.data.between(ex.data_inicio, ex.data_fim),
               Agendamento.status.in_(STATUS_OCUPAM - {StatusAgendamento.COMPARECEU}))
        .options(selectinload(Agendamento.itens))
    )
    saida = []
    for ag in s.scalars(consulta):
        if agora_passou(ag):  # quem já passou do horário não tem o que remarcar
            continue
        if ex.turno is not None and ag.turno != ex.turno:
            continue
        if ex.profissional_id is None or any(i.profissional_id == ex.profissional_id for i in ag.itens):
            saida.append(ag)
    return saida


def avisar_remarcacao(s: Session, ags: list[Agendamento]) -> int:
    """Põe na fila o aviso de remarcação. Quem já foi avisado não recebe de novo, e o lembrete do dia
    anterior é cancelado (não faz sentido lembrar de um exame que precisa mudar de dia)."""
    n = 0
    for ag in ags:
        if not ag.contato_id:
            continue
        avisos = list(s.scalars(select(Notificacao).where(Notificacao.agendamento_id == ag.id)))
        for a in avisos:
            if a.tipo == TipoNotificacao.LEMBRETE_D1 and a.status == StatusNotificacao.AGENDADA:
                a.status, a.erro = StatusNotificacao.CANCELADA, "exame precisa ser remarcado"
        if any(a.tipo == TipoNotificacao.REMARCAR and a.status != StatusNotificacao.CANCELADA for a in avisos):
            continue
        s.add(Notificacao(tipo=TipoNotificacao.REMARCAR, contato_id=ag.contato_id,
                          agendamento_id=ag.id, enviar_em=agora()))
        n += 1
    return n


def contato_por_telefone(s: Session, telefone: str) -> Contato | None:
    return s.scalar(select(Contato).where(Contato.telefone == telefone))


def agora_passou(ag: Agendamento) -> bool:
    return datetime.combine(ag.data, ag.horario) <= agora()
