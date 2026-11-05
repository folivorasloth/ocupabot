"""Vocabulário fechado do sistema. Gravado como texto no banco."""

from enum import StrEnum


class Perfil(StrEnum):
    ADMIN = "ADMIN"
    SUPERVISAO = "SUPERVISAO"
    RECEPCAO = "RECEPCAO"
    LEITURA = "LEITURA"


class Turno(StrEnum):
    MANHA = "MANHA"
    TARDE = "TARDE"


class TipoContato(StrEnum):
    RH = "RH"
    PARTICULAR = "PARTICULAR"
    PACIENTE = "PACIENTE"
    DESCONHECIDO = "DESCONHECIDO"


class StatusAgendamento(StrEnum):
    AGUARDANDO_APROVACAO = "AGUARDANDO_APROVACAO"
    AGENDADO = "AGENDADO"
    CONFIRMADO = "CONFIRMADO"
    COMPARECEU = "COMPARECEU"
    FALTOU = "FALTOU"
    CANCELADO = "CANCELADO"
    REMARCADO = "REMARCADO"


# Status que seguram a vaga
STATUS_OCUPAM = {
    StatusAgendamento.AGUARDANDO_APROVACAO,
    StatusAgendamento.AGENDADO,
    StatusAgendamento.CONFIRMADO,
    StatusAgendamento.COMPARECEU,
}
STATUS_ATIVOS = {StatusAgendamento.AGENDADO, StatusAgendamento.CONFIRMADO}


class Origem(StrEnum):
    WHATSAPP = "WHATSAPP"
    PAINEL = "PAINEL"
    IMPORTACAO = "IMPORTACAO"


class TipoAprovacao(StrEnum):
    NOVO = "NOVO"
    REMARCACAO = "REMARCACAO"
    CANCELAMENTO = "CANCELAMENTO"


class StatusAprovacao(StrEnum):
    PENDENTE = "PENDENTE"
    APROVADA = "APROVADA"
    RECUSADA = "RECUSADA"


class TipoExcecao(StrEnum):
    FERIAS = "FERIAS"
    FOLGA = "FOLGA"
    AUSENCIA = "AUSENCIA"
    FERIADO = "FERIADO"


class EstadoConversa(StrEnum):
    BOT = "BOT"
    AGUARDANDO_HUMANO = "AGUARDANDO_HUMANO"
    HUMANO = "HUMANO"


class Autor(StrEnum):
    CONTATO = "CONTATO"
    BOT = "BOT"
    EQUIPE = "EQUIPE"
    SISTEMA = "SISTEMA"


class StatusEnvio(StrEnum):
    RECEBIDA = "RECEBIDA"  # mensagem de entrada
    PENDENTE = "PENDENTE"
    ENVIADA = "ENVIADA"
    FALHOU = "FALHOU"
    EXPIRADA = "EXPIRADA"
    BLOQUEADA = "BLOQUEADA"  # modo teste ou opt-out
    SIMULADA = "SIMULADA"  # simulador do painel


class TipoNotificacao(StrEnum):
    CONFIRMACAO = "CONFIRMACAO"
    LEMBRETE_D1 = "LEMBRETE_D1"
    FALTA = "FALTA"
    REMARCAR = "REMARCAR"


class StatusNotificacao(StrEnum):
    AGENDADA = "AGENDADA"
    ENVIADA = "ENVIADA"
    RESPONDIDA = "RESPONDIDA"
    CANCELADA = "CANCELADA"
    FALHOU = "FALHOU"
