"""Sistema de gestão externo (a agenda oficial da clínica), atrás de uma interface.

Cada clínica usa um sistema diferente. Para integrar um novo, implemente `AgendaExterna`
(leitura da ocupação e, opcionalmente, gravação). O `Simulador` serve de exemplo e de teste.

Regras que valem para qualquer implementação:
  * sem leitura válida e recente, o bot não oferece horário (o externo tem prioridade);
  * horário ocupado no externo nunca é oferecido pelo bot;
  * do CPF lido, só fica um hash com sal.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, time, timedelta
from typing import Protocol

from ..config import config


@dataclass(frozen=True)
class Compromisso:
    data: date
    horario: time
    codigo: str
    cpf: str | None = None


class ErroLeitura(Exception):
    pass


class AgendaExterna(Protocol):
    def ler(self, de: date, ate: date) -> list[Compromisso]: ...


class Simulador:
    """Agenda externa fictícia e determinística: alguns horários ocupados por dia útil."""

    def __init__(self, semente: int = 42, falhar: bool = False) -> None:
        self.semente = semente
        self.falhar = falhar
        self.extras: list[Compromisso] = []

    def ler(self, de: date, ate: date) -> list[Compromisso]:
        if self.falhar:
            raise ErroLeitura("simulador configurado para falhar")
        saida = list(c for c in self.extras if de <= c.data <= ate)
        d = de
        while d <= ate:
            if d.weekday() < 5:
                rnd = random.Random(f"{self.semente}-{d.isoformat()}")
                for i in range(2):
                    h = time(rnd.choice([8, 9, 10, 14, 15]), rnd.choice([0, 20, 40]))
                    saida.append(Compromisso(d, h, f"SIM-{d:%m%d}-{i}"))
            d += timedelta(days=1)
        return saida


_agenda: AgendaExterna | None = None


def agenda_externa() -> AgendaExterna | None:
    global _agenda
    if _agenda is None and config().agenda_externa == "simulador":
        _agenda = Simulador()
    return _agenda


def definir_agenda_externa(a: AgendaExterna | None) -> None:
    global _agenda
    _agenda = a
