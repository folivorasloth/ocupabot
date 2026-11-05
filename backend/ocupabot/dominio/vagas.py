"""Motor de vagas — puro, sem banco.

Uma vaga existe no horário H do dia D para um conjunto de funções F quando:
  * H cabe no expediente do dia (turno manhã ou tarde);
  * não há exceção da clínica inteira (feriado) naquele dia/turno;
  * para cada função de F existe um profissional DIFERENTE que
      - está na grade confirmada daquele dia da semana e turno para aquela função,
      - não tem exceção (férias, folga, ausência) cobrindo o dia/turno,
      - não está ocupado exatamente em H, e
      - ainda não atingiu a capacidade por hora da função naquela hora do relógio.

O profissional é um recurso único: se atende clínico e audiometria, uma ocupação em qualquer das
duas o tira das duas. Agendamentos já existentes sem profissional definido (ex.: importados)
entram como demanda extra da função no mesmo horário e também precisam de alguém livre.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta


@dataclass(frozen=True)
class Ocupacao:
    data: date
    horario: time
    funcao_id: int | None
    profissional_id: int | None


@dataclass(frozen=True)
class Indisponibilidade:
    profissional_id: int | None  # None = a clínica inteira
    inicio: date
    fim: date
    turno: str | None  # None = o dia todo

    def cobre(self, d: date, turno: str) -> bool:
        return self.inicio <= d <= self.fim and (self.turno is None or self.turno == turno)


@dataclass
class Retrato:
    """Tudo o que o cálculo precisa, carregado uma vez para um intervalo de datas."""

    expediente: dict[tuple[int, str], tuple[time, time]]
    grade: dict[tuple[int, str, int], set[int]]  # (dia_semana, turno, funcao) -> profissionais
    capacidade: dict[int, int]  # funcao -> pacientes por hora por profissional
    passo_min: int = 10
    excecoes: list[Indisponibilidade] = field(default_factory=list)
    ocupacoes: list[Ocupacao] = field(default_factory=list)
    bloqueios: set[tuple[date, time]] = field(default_factory=set)

    def __post_init__(self) -> None:
        self._por_horario: dict[tuple[date, time], list[Ocupacao]] = defaultdict(list)
        self._por_hora: dict[tuple[date, int, int], int] = defaultdict(int)
        for o in self.ocupacoes:
            self._por_horario[(o.data, o.horario)].append(o)
            if o.profissional_id is not None:
                self._por_hora[(o.data, o.horario.hour, o.profissional_id)] += 1

    # --- consultas básicas ---------------------------------------------------------------------------

    def turno_de(self, d: date, t: time) -> str | None:
        fim_slot = (datetime.combine(d, t) + timedelta(minutes=self.passo_min)).time()
        for (dia, turno), (ini, fim) in self.expediente.items():
            if dia == d.weekday() and ini <= t and fim_slot <= fim and fim_slot > t:
                return turno
        return None

    def horarios_do_dia(self, d: date) -> list[tuple[time, str]]:
        saida = []
        for (dia, turno), (ini, fim) in sorted(self.expediente.items(), key=lambda kv: kv[1][0]):
            if dia != d.weekday():
                continue
            atual = datetime.combine(d, ini)
            limite = datetime.combine(d, fim)
            while atual + timedelta(minutes=self.passo_min) <= limite:
                saida.append((atual.time(), turno))
                atual += timedelta(minutes=self.passo_min)
        return saida

    def _ausente(self, prof: int | None, d: date, turno: str) -> bool:
        return any(e.profissional_id == prof and e.cobre(d, turno) for e in self.excecoes)

    def profissionais(self, d: date, turno: str, funcao_id: int) -> set[int]:
        base = self.grade.get((d.weekday(), turno, funcao_id), set())
        return {p for p in base if not self._ausente(p, d, turno)}

    # --- o cálculo ----------------------------------------------------------------------------------

    def atribuir(
        self, d: date, t: time, funcoes: list[int], bloquear_externos: bool = True
    ) -> dict[int, int] | None:
        """Escolhe um profissional diferente para cada função; None se o horário não serve."""
        turno = self.turno_de(d, t)
        if turno is None or self._ausente(None, d, turno):
            return None
        if bloquear_externos and (d, t) in self.bloqueios:
            return None
        if not funcoes:
            return {}

        ocup = self._por_horario.get((d, t), [])
        ocupados = {o.profissional_id for o in ocup if o.profissional_id is not None}
        demanda_antiga = [o.funcao_id for o in ocup if o.profissional_id is None and o.funcao_id]

        candidatos: dict[int, list[int]] = {}
        for f in set(funcoes) | set(demanda_antiga):
            cap = self.capacidade.get(f, 60 // self.passo_min)
            livres = [
                p
                for p in sorted(self.profissionais(d, turno, f))
                if p not in ocupados and self._por_hora[(d, t.hour, p)] < cap
            ]
            candidatos[f] = livres

        # demandas antigas primeiro (já existem e precisam continuar cabendo), depois as novas,
        # das funções com menos opções para as com mais.
        pedidas = list(funcoes)
        demandas = [(f, False) for f in demanda_antiga] + [(f, True) for f in pedidas]
        demandas.sort(key=lambda x: (x[1], len(candidatos[x[0]])))

        escolha: dict[int, int] = {}
        usados: set[int] = set()

        def tentar(i: int) -> bool:
            if i == len(demandas):
                return True
            f, nova = demandas[i]
            for p in candidatos[f]:
                if p in usados:
                    continue
                usados.add(p)
                if nova:
                    escolha[f] = p
                if tentar(i + 1):
                    return True
                usados.discard(p)
                if nova:
                    escolha.pop(f, None)
            return False

        return dict(escolha) if tentar(0) else None

    def livres_no_dia(
        self,
        d: date,
        funcoes: list[int],
        nao_antes: datetime | None = None,
        bloquear_externos: bool = True,
    ) -> list[time]:
        saida = []
        for t, _turno in self.horarios_do_dia(d):
            if nao_antes is not None and datetime.combine(d, t) <= nao_antes:
                continue
            if self.atribuir(d, t, funcoes, bloquear_externos) is not None:
                saida.append(t)
        return saida


def agrupar_faixas(horarios: list[time], passo_min: int) -> list[tuple[time, time]]:
    """[07:30, 07:40, 07:50, 09:00] -> [(07:30, 07:50), (09:00, 09:00)]"""
    faixas: list[tuple[time, time]] = []
    for t in sorted(horarios):
        if faixas:
            ini, fim = faixas[-1]
            prox = (datetime.combine(date.min, fim) + timedelta(minutes=passo_min)).time()
            if prox == t:
                faixas[-1] = (ini, t)
                continue
        faixas.append((t, t))
    return faixas
