"""Parâmetros da clínica, editáveis no painel. Tudo o que age sozinho nasce desligado."""

import re
from datetime import time

from sqlalchemy.orm import Session

from ..modelos import Parametro

PADROES: dict[str, tuple[str, str]] = {
    "aprovacao_equipe": ("true", "Pedidos do bot (novo, remarcação, cancelamento) esperam a equipe aprovar."),
    "envios_automaticos": ("false", "Trava geral: false = nenhum lembrete/aviso automático sai sozinho."),
    "exige_leitura_externa": (
        "true",
        "Sem leitura válida e recente da agenda externa, o bot não oferece horário e chama a equipe.",
    ),
    "leitura_externa_validade_min": ("30", "Minutos que uma leitura da agenda externa continua valendo."),
    "bloquear_horario_externo": ("true", "Horário ocupado na agenda externa não é oferecido pelo bot."),
    "passo_min": ("10", "Intervalo entre horários da agenda, em minutos."),
    "capacidade_padrao_por_hora": ("6", "Pacientes por hora por profissional quando a função não define."),
    "prazo_maximo_dias": ("21", "Até quantos dias à frente o bot oferece horário."),
    "agenda_max_dias_futuro": ("365", "Até quantos dias à frente a equipe agenda, remarca ou propõe pelo painel."),
    "antecedencia_minima_min": (
        "60",
        "Minutos de antecedência para o bot oferecer um horário (pedido às 15:45 não recebe 16:10). "
        "A equipe pode marcar em cima da hora pelo painel.",
    ),
    "dias_lista_horarios": ("5", "Quantos dias com vaga o bot lista quando a sugestão é recusada."),
    "erros_ate_humano": ("3", "Mensagens não entendidas seguidas antes de chamar a equipe."),
    "fluxo_expira_horas": ("12", "Horas sem resposta para um fluxo largado recomeçar do menu."),
    "agrupar_mensagens_segundos": (
        "8",
        "Segundos que o bot espera depois da última mensagem de um número antes de responder: quem escreve "
        "várias mensagens seguidas recebe UMA resposta. 0 = responde cada mensagem na hora.",
    ),
    "proposta_validade_horas": (
        "24",
        "Horas que a pessoa tem para responder à proposta de outro horário. Vence antes se faltarem menos de "
        "2 h para o exame. Vencida, a vaga é liberada e vira alerta (sem mensagem automática).",
    ),
    "lembrete_hora": ("16:00", "Hora do lembrete enviado no dia anterior ao exame."),
    "lembrete_limite_hora": (
        "20:00",
        "Quem marca para amanhã depois da hora do lembrete recebe o lembrete logo, se ainda for antes deste "
        "horário. Depois dele, só a confirmação.",
    ),
    "resposta_bot_validade_horas": ("2", "Resposta do bot que não saiu até este prazo é descartada."),
    "resposta_equipe_validade_horas": ("24", "Resposta da equipe que não saiu até este prazo expira."),
    "pcmso_alerta_dias": ("30", "A tela Hoje avisa o PCMSO de empresa que vence dentro deste prazo."),
    "alerta_seguranca_limite": (
        "10",
        "Logins ou webhooks recusados nas últimas 24 h acima deste número viram alerta para o administrador.",
    ),
    "orientacoes": ("Chegue com 10 minutos de antecedência e traga documento com foto.",
                    "Texto no fim da confirmação do agendamento."),
    "horario_atendimento": ("seg a sex, 7h30–11h30 e 13h30–16h30", "Horário da equipe, usado nas mensagens."),
}

# Faixa aceita nos parâmetros numéricos, na escrita e na leitura (valor fora da faixa volta ao padrão)
FAIXAS: dict[str, tuple[int, int]] = {
    "leitura_externa_validade_min": (1, 1440),
    "passo_min": (5, 120),
    "capacidade_padrao_por_hora": (1, 60),
    "prazo_maximo_dias": (1, 365),
    "agenda_max_dias_futuro": (1, 3650),
    "antecedencia_minima_min": (0, 1440),
    "dias_lista_horarios": (1, 14),
    "erros_ate_humano": (1, 10),
    "fluxo_expira_horas": (1, 168),
    "agrupar_mensagens_segundos": (0, 30),
    "proposta_validade_horas": (1, 168),
    "resposta_bot_validade_horas": (1, 72),
    "resposta_equipe_validade_horas": (1, 168),
    "pcmso_alerta_dias": (1, 365),
    "alerta_seguranca_limite": (1, 100000),
}
HORAS = {"lembrete_hora", "lembrete_limite_hora"}
_HORA = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def problema(chave: str, valor: str) -> str | None:
    """None se o valor serve para o parâmetro; senão, a explicação para a tela."""
    padrao = PADROES.get(chave, ("",))[0]
    if padrao in ("true", "false"):
        return None if valor in ("true", "false") else "use true ou false"
    if chave in FAIXAS:
        minimo, maximo = FAIXAS[chave]
        if not (valor.isascii() and valor.isdigit() and minimo <= int(valor) <= maximo):
            return f"use um número inteiro de {minimo} a {maximo}"
    if chave in HORAS and not _HORA.match(valor):
        return "use a hora no formato HH:MM"
    if not valor.strip():
        return "o valor não pode ficar vazio"
    return None


def garantir_padroes(s: Session) -> None:
    existentes = {p.chave for p in s.query(Parametro.chave)}
    for chave, (valor, desc) in PADROES.items():
        if chave not in existentes:
            s.add(Parametro(chave=chave, valor=valor, descricao=desc))
    s.flush()


def texto(s: Session, chave: str) -> str:
    p = s.get(Parametro, chave)
    if p is not None:
        return p.valor
    return PADROES[chave][0]


def inteiro(s: Session, chave: str) -> int:
    valor = texto(s, chave)
    return int(PADROES[chave][0]) if problema(chave, valor) or not valor.isdigit() else int(valor)


def hora(s: Session, chave: str) -> time:
    valor = texto(s, chave)
    return time.fromisoformat(valor if _HORA.match(valor) else PADROES[chave][0])


def ligado(s: Session, chave: str) -> bool:
    return texto(s, chave).strip().lower() in {"1", "true", "sim", "s", "yes", "on"}
