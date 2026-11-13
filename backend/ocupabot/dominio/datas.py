"""Leitura de datas e horas digitadas pela pessoa e formatação curta para as mensagens."""

import re
from datetime import date, datetime, time, timedelta

from .texto import normalizar

DIAS = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]
_SEMANA = {"segunda": 0, "terca": 1, "quarta": 2, "quinta": 3, "sexta": 4, "sabado": 5, "domingo": 6}


def _falada(texto: str, hoje: date) -> date | None:
    """'amanhã', 'depois de amanhã', 'sexta', 'dia 12': a data como a pessoa fala."""
    n = normalizar(texto)
    palavras = n.split()
    if "depois de amanha" in n:
        return hoje + timedelta(days=2)
    if "amanha" in palavras:
        return hoje + timedelta(days=1)
    if "hoje" in palavras:
        return hoje
    for nome, dia in _SEMANA.items():
        if nome in palavras:
            return hoje + timedelta(days=(dia - hoje.weekday() - 1) % 7 + 1)
    m = re.search(r"\bdia (\d{1,2})\b", n)
    if m:
        for mes in range(2):  # este mês ou, se o dia já passou, o próximo
            ano, mes_ = divmod(hoje.month - 1 + mes, 12)
            try:
                d = date(hoje.year + ano, mes_ + 1, int(m.group(1)))
            except ValueError:
                continue
            if d >= hoje:
                return d
    return None


def ler_data(texto: str, hoje: date) -> date | None:
    """Aceita dd/mm, dd/mm/aa, dd/mm/aaaa e a data falada. Sem ano, assume o próximo dia/mês a partir de hoje."""
    m = re.search(r"(?<!\d)(\d{1,2})[/\-.](\d{1,2})(?:[/\-.](\d{2,4}))?(?!\d)", texto or "")
    if not m:
        return _falada(texto or "", hoje)
    dia, mes, ano = int(m.group(1)), int(m.group(2)), m.group(3)
    try:
        if ano:
            a = int(ano)
            if a < 100:
                a += 2000
            return date(a, mes, dia)
        candidata = date(hoje.year, mes, dia)
        if candidata < hoje:
            candidata = date(hoje.year + 1, mes, dia)
        return candidata
    except ValueError:
        return None


def ler_nascimento(texto: str, hoje: date) -> date | None:
    m = re.search(r"(?<!\d)(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})(?!\d)", texto or "")
    if not m:
        return None
    dia, mes, a = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if a < 100:
        a += 1900 if a > hoje.year % 100 else 2000
    try:
        d = date(a, mes, dia)
    except ValueError:
        return None
    if not (hoje.year - 110 <= d.year and d <= hoje):
        return None
    return d


def ler_hora(texto: str) -> time | None:
    """Acha uma hora como 7:30, 07h30, 13h ou 1330, ignorando a data (dd/mm)."""
    sem_data = re.sub(r"\d{1,2}[/\-.]\d{1,2}(?:[/\-.]\d{2,4})?|\bdia \d{1,2}\b", " ", texto or "",
                      flags=re.IGNORECASE)
    m = re.search(r"(?<!\d)(\d{1,2})\s*(?:[:h]\s*(\d{2})?|(\d{2}))(?!\d)", sem_data)
    if not m:
        return None
    h = int(m.group(1))
    mi = int(m.group(2) or m.group(3) or 0)
    if h > 23 or mi > 59:
        return None
    return time(h, mi)


def curta(d: date) -> str:
    return f"{DIAS[d.weekday()]} {d:%d/%m}"


def hora(t: time) -> str:
    return f"{t:%H:%M}"


def combinar(d: date, t: time) -> datetime:
    return datetime.combine(d, t)
