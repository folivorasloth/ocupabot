"""Parâmetros da clínica, editáveis no painel. Tudo o que age sozinho nasce desligado."""

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
    "dias_lista_horarios": ("5", "Quantos dias com vaga o bot lista quando a sugestão é recusada."),
    "erros_ate_humano": ("3", "Mensagens não entendidas seguidas antes de chamar a equipe."),
    "fluxo_expira_horas": ("12", "Horas sem resposta para um fluxo largado recomeçar do menu."),
    "lembrete_hora": ("16:00", "Hora do lembrete enviado no dia anterior ao exame."),
    "resposta_bot_validade_horas": ("2", "Resposta do bot que não saiu até este prazo é descartada."),
    "resposta_equipe_validade_horas": ("24", "Resposta da equipe que não saiu até este prazo expira."),
    "orientacoes": ("Chegue com 10 minutos de antecedência e traga documento com foto.",
                    "Texto no fim da confirmação do agendamento."),
    "horario_atendimento": ("seg a sex, 7h30–11h30 e 13h30–16h30", "Horário da equipe, usado nas mensagens."),
}


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
    try:
        return int(texto(s, chave))
    except ValueError:
        return int(PADROES[chave][0])


def ligado(s: Session, chave: str) -> bool:
    return texto(s, chave).strip().lower() in {"1", "true", "sim", "s", "yes", "on"}
