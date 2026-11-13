"""Vocabulário fechado do sistema. Gravado como texto no banco."""

from enum import StrEnum


class Perfil(StrEnum):
    ADMIN = "ADMIN"
    SUPERVISAO = "SUPERVISAO"
    RECEPCAO = "RECEPCAO"


class Turno(StrEnum):
    MANHA = "MANHA"
    TARDE = "TARDE"


class TipoContato(StrEnum):
    RH = "RH"
    CREDENCIADORA = "CREDENCIADORA"
    CONTABILIDADE = "CONTABILIDADE"
    PARTICULAR = "PARTICULAR"
    PACIENTE = "PACIENTE"
    DESCONHECIDO = "DESCONHECIDO"


# Quem agenda em nome de empresas (um escritório de contabilidade agenda por várias)
AGENDA_PELA_EMPRESA = {TipoContato.RH, TipoContato.CREDENCIADORA, TipoContato.CONTABILIDADE}


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
    AGUARDANDO_CLIENTE = "AGUARDANDO_CLIENTE"  # a equipe propôs outro horário e espera a resposta
    EXPIRADA = "EXPIRADA"  # a proposta venceu sem resposta


APROVACAO_EM_ABERTO = {StatusAprovacao.PENDENTE, StatusAprovacao.AGUARDANDO_CLIENTE}


class PcmsoElaboradoPor(StrEnum):
    """Quem fez o PCMSO da empresa. Vazio no cadastro = não acompanhado."""

    CLINICA = "CLINICA"
    TERCEIRO = "TERCEIRO"  # outra empresa elaborou: a cliente precisa mandar o documento em vigor


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
