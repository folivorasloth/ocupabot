"""Comandos da equipe pelo WhatsApp.

Quem é da equipe: usuário ATIVO do painel com o WhatsApp cadastrado (Usuários → WhatsApp). Qualquer outro
número continua sendo cliente. Mensagem da equipe que não é comando segue para o bot de sempre.

Comandos (o dia é hoje, a não ser que venha outro: "ontem", "12/11", "amanhã"):
  "paciente das 14h compareceu" / "chegou" / "veio"        -> presença
  "das 14h faltou" / "não veio" / "Ana Lima faltou"         -> falta (quem agendou é avisado)
  "das 14h cancelou" / "cancelar o das 14:30"               -> cancelar
  "das 14h remarcou para 12/11 9h"                          -> remarcar
  "agenda", "agenda de amanhã", "quem vem amanhã"           -> lista do dia
  "ajuda" / "comandos"                                      -> esta lista

Nada muda sem o SIM: o bot repete o que entendeu e espera a confirmação (vale 10 minutos). Valem as
mesmas regras do painel: presença e falta só a partir do dia; cancelar ou remarcar o que já está no
sistema externo só a Supervisão. Tudo vai para a auditoria com o usuário e o ator "whatsapp_equipe".
"""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..dominio import datas
from ..dominio.texto import normalizar, variantes
from ..enums import STATUS_ATIVOS, Perfil, StatusAgendamento
from ..modelos import Agendamento, Usuario
from ..relogio import agora
from ..servicos import agenda
from . import intencoes as it

if TYPE_CHECKING:
    from .maquina import Bot

ATOR = "whatsapp_equipe"
VALIDADE = timedelta(minutes=10)

# a ordem importa: "não veio" antes de "veio", "não compareceu" antes de "compareceu"
ACOES = [
    ("FALTA", re.compile(r"\b(faltou|falta|nao veio|nao compareceu|nao apareceu|ausente|nao chegou)\b")),
    ("REMARCAR", re.compile(r"\b(remarcou|remarcar|remarca|reagendou|reagendar|passar|passa|mudar|muda|mudou)\b")),
    ("CANCELAR", re.compile(r"\b(cancelou|cancelar|cancela|desmarcou|desmarcar|desmarca)\b")),
    ("PRESENCA", re.compile(r"\b(compareceu|chegou|veio|presente|presenca|atendido|atendida)\b")),
]
AGENDA = re.compile(r"^(agenda|quem vem|quem tem|lista|pacientes)\b")
AJUDA = {"ajuda", "comandos", "equipe", "comandos da equipe", "menu equipe"}
ROTULO = {"PRESENCA": "marcar COMPARECEU", "FALTA": "marcar FALTA", "CANCELAR": "CANCELAR", "REMARCAR": "REMARCAR"}
STATUS = {StatusAgendamento.AGENDADO: "agendado", StatusAgendamento.CONFIRMADO: "confirmado",
          StatusAgendamento.COMPARECEU: "compareceu", StatusAgendamento.FALTOU: "faltou",
          StatusAgendamento.AGUARDANDO_APROVACAO: "esperando aprovação"}
# o que sobra depois de tirar a ação, a hora e a data, e não é nome de paciente
NAO_E_NOME = {"paciente", "o", "a", "do", "da", "das", "dos", "de", "as", "hoje", "amanha", "ontem", "h", "hs",
              "hora", "horas", "e", "que", "ja", "nao", "para", "pra", "agendamento", "exame", "consulta", "dia",
              "senhor", "senhora", "sr", "sra", "funcionario", "funcionaria", "por", "favor", "segunda", "terca",
              "quarta", "quinta", "sexta", "sabado", "domingo", "feira", "manha", "tarde", "no", "na", "em"}
NAO_E_NOME.update(p for _, r in ACOES for p in re.findall(r"[a-z]+", r.pattern))
AJUDA_TEXTO = ("Comandos da equipe (o dia é hoje, a não ser que você diga outro):\n"
               "• paciente das 14h compareceu\n• das 14h faltou\n• das 14:30 cancelou\n"
               "• das 14h remarcou para 12/11 9h\n• agenda (ou: agenda de amanhã)\n"
               "Também vale o nome: \"Ana Lima faltou\". Nada muda sem o seu SIM.")


def usuario_do_numero(s: Session, telefone: str) -> Usuario | None:
    return s.scalar(select(Usuario).where(Usuario.whatsapp.in_(variantes(telefone)), Usuario.ativo.is_(True)))


def ler_hora(t: str) -> time | None:
    """'14h', '14:30', 'das 14', 'às 9' -> hora."""
    h = datas.ler_hora(t)
    if h is None:
        m = re.search(r"\b(?:das|dos|da|do|as|a)\s+(\d{1,2})\b(?![/:h])", normalizar(t))
        h = time(int(m.group(1))) if m and int(m.group(1)) < 24 else None
    return h


def ler_dia(t: str, hoje: date) -> date | None:
    if "ontem" in normalizar(t).split():
        return hoje - timedelta(days=1)
    return datas.ler_data(t, hoje)


def curto(nome: str) -> str:
    """'Ana Fictícia Souza' -> 'Ana S.' (o WhatsApp leva o mínimo do paciente)."""
    p = nome.title().split()
    return p[0] if len(p) == 1 else f"{p[0]} {p[-1][0]}."


def _quando(d: date, h: time | None = None) -> str:
    return datas.curta(d) + (f" às {datas.hora(h)}" if h else "")


class Equipe:
    def __init__(self, bot: Bot, usuario: Usuario) -> None:
        self.bot, self.u, self.s = bot, usuario, bot.s
        self.agora = agora()

    def diz(self, t: str) -> None:
        self.bot.dizer(t)

    def guardar(self, pendente: dict | None) -> None:
        if pendente is None:
            self.bot.d.pop("equipe", None)
        else:
            self.bot.d["equipe"] = pendente

    # --- entrada -----------------------------------------------------------------------------------

    def processar(self, msg: str) -> bool:
        """True = era comando da equipe (ou resposta a um) e já respondeu. False = segue para o bot."""
        n = normalizar(msg)
        pend = self.bot.d.get("equipe")
        if pend and datetime.fromisoformat(pend["expira"]) >= self.agora:
            if pend.get("opcoes") is not None and n.isdigit():
                return self._escolheu(pend, int(n))
            if pend.get("ag") is not None and it.eh_sim(msg):
                return self._executar(pend)
            if it.eh_nao(msg):
                self.guardar(None)
                self.diz("Certo, nada foi alterado.")
                return True
        if n in AJUDA:
            self.diz(AJUDA_TEXTO)
            return True
        if AGENDA.match(n):
            self._agenda(ler_dia(msg, self.agora.date()) or self.agora.date())
            return True
        acao = next((a for a, r in ACOES if r.search(n)), None)
        if acao is None:
            return False
        self._pedido(acao, msg)
        return True

    # --- agenda do dia -----------------------------------------------------------------------------

    def _agenda(self, d: date) -> None:
        ags = list(self.s.scalars(select(Agendamento).where(
            Agendamento.data == d, Agendamento.status.in_(list(STATUS))).order_by(Agendamento.horario)))
        if not ags:
            self.diz(f"{_quando(d).capitalize()}: ninguém marcado.")
            return
        linhas = [f"{datas.hora(a.horario)} {curto(a.paciente.nome)} ({STATUS[a.status]})" for a in ags[:40]]
        extra = f"\n… e mais {len(ags) - 40}: veja no painel." if len(ags) > 40 else ""
        self.diz(f"{_quando(d).capitalize()} ({len(ags)}):\n" + "\n".join(linhas) + extra)

    # --- pedido: acha o agendamento e pede o SIM -----------------------------------------------------

    def _pedido(self, acao: str, msg: str) -> None:
        alvo, destino = msg, ""
        if acao == "REMARCAR":
            partes = re.split(r"\b(?:para|pra|p/)\b", msg, maxsplit=1, flags=re.IGNORECASE)
            alvo, destino = partes[0], (partes[1] if len(partes) > 1 else "")
        hoje = self.agora.date()
        dia = ler_dia(alvo, hoje) or hoje
        h = ler_hora(alvo)
        nome = [p for p in normalizar(re.sub(r"\d{1,2}\s*[:hH/]\s*\d{0,2}", " ", alvo)).split()
                if len(p) >= 2 and not p.isdigit() and p not in NAO_E_NOME]
        if h is None and not nome:
            self.diz("De qual paciente? Mande a hora ou o nome, ex.: \"das 14h faltou\" ou \"Ana Lima faltou\". "
                     "Para ver o dia, mande AGENDA.")
            return
        nova = None
        if acao == "REMARCAR":
            nh = ler_hora(destino)
            if nh is None:
                self.diz("Para quando? Mande junto o novo dia e hora, ex.: \"das 14h remarcou para 12/11 9h\".")
                return
            nova = [(ler_dia(destino, hoje) or dia).isoformat(), datas.hora(nh)]
        consulta = select(Agendamento).where(Agendamento.data == dia, Agendamento.status.in_(STATUS_ATIVOS))
        if h is not None:
            consulta = consulta.where(Agendamento.horario == h)
        achados = list(self.s.scalars(consulta.order_by(Agendamento.horario)))
        if nome:
            achados = [a for a in achados
                       if all(any(w.startswith(t) for w in normalizar(a.paciente.nome).split()) for t in nome)]
        if not achados:
            quem = f", {' '.join(nome).title()}" if nome else ""
            self.diz(f"Não achei agendamento ativo ({_quando(dia, h)}{quem}). Mande AGENDA para ver o dia.")
            return
        base = {"acao": acao, "nova": nova, "expira": (self.agora + VALIDADE).isoformat()}
        if len(achados) > 1:
            self.guardar({**base, "opcoes": [a.id for a in achados[:9]]})
            ops = "\n".join(f"{i}) {datas.hora(a.horario)} {curto(a.paciente.nome)}"
                            for i, a in enumerate(achados[:9], 1))
            self.diz(f"Achei mais de um ({_quando(dia, h)}). Qual?\n{ops}\nResponda com o número.")
            return
        self._confirmar({**base, "ag": achados[0].id})

    def _escolheu(self, pend: dict, i: int) -> bool:
        ops = pend.get("opcoes") or []
        if not 1 <= i <= len(ops):
            self.diz("Responda com um dos números da lista.")
            return True
        self._confirmar({k: v for k, v in pend.items() if k != "opcoes"} | {"ag": ops[i - 1]})
        return True

    def _bloqueado_no_externo(self, ag: Agendamento, acao: str) -> bool:
        return (acao in ("CANCELAR", "REMARCAR") and ag.no_sistema_externo
                and self.u.perfil not in (Perfil.SUPERVISAO, Perfil.ADMIN))

    def _confirmar(self, pend: dict) -> None:
        ag = self.s.get(Agendamento, pend["ag"])
        tipo = ag.tipo_aso.nome if ag.tipo_aso else "exames"
        empresa = (ag.empresa.nome_fantasia or ag.empresa.razao_social) if ag.empresa else "particular"
        linha = f"{curto(ag.paciente.nome)}, {_quando(ag.data, ag.horario)} ({tipo}, {empresa})"
        acao = pend["acao"]
        if self._bloqueado_no_externo(ag, acao):
            self.guardar(None)
            self.diz(f"{linha} está no sistema externo: cancelar ou remarcar é só com a Supervisão.")
            return
        o_que = ROTULO[acao]
        if acao == "REMARCAR":
            o_que += f" para {_quando(date.fromisoformat(pend['nova'][0]))} às {pend['nova'][1]}"
        aviso = ""
        if acao in ("FALTA", "REMARCAR") and ag.contato is not None and ag.contato.optout_em is None:
            aviso = "\nQuem agendou recebe o aviso pelo WhatsApp."
        self.guardar(pend)
        self.diz(f"{linha}: {o_que}?{aviso}\nResponda SIM para confirmar ou NÃO.")

    # --- SIM: faz, com as mesmas regras do painel ----------------------------------------------------

    def _executar(self, pend: dict) -> bool:
        self.guardar(None)
        ag = self.s.get(Agendamento, pend["ag"])
        acao = pend["acao"]
        final = ag
        try:
            with self.s.begin_nested():
                if self._bloqueado_no_externo(ag, acao):
                    raise agenda.OperacaoInvalida("está no sistema externo: só a Supervisão altera")
                if acao == "PRESENCA":
                    agenda.presenca(self.s, ag, self.u.id, ATOR)
                elif acao == "FALTA":
                    agenda.falta(self.s, ag, self.u.id, ATOR)
                elif acao == "CANCELAR":
                    agenda.cancelar(self.s, ag, "Cancelado pela equipe (WhatsApp)", self.u.id, ATOR)
                else:
                    d, h = date.fromisoformat(pend["nova"][0]), time.fromisoformat(pend["nova"][1])
                    final = agenda.remarcar(self.s, ag, d, h, self.u.id, ATOR)
        except (agenda.VagaIndisponivel, agenda.OperacaoInvalida) as e:
            self.diz(f"Não deu: {e}.")
            return True
        feito = {"PRESENCA": "marcado como COMPARECEU", "FALTA": "marcado como FALTA", "CANCELAR": "CANCELADO",
                 "REMARCAR": f"REMARCADO para {_quando(final.data, final.horario)}"}[acao]
        self.diz(f"Feito: {curto(ag.paciente.nome)} {feito}.")
        return True
