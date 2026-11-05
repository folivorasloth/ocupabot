"""Leitura de datas e horas digitadas pela pessoa e formatação curta para as mensagens."""

import re
from datetime import date, datetime, time

DIAS = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]


def ler_data(texto: str, hoje: date) -> date | None:
    """Aceita dd/mm, dd/mm/aa e dd/mm/aaaa. Sem ano, assume o próximo dia/mês a partir de hoje."""
    m = re.search(r"(?<!\d)(\d{1,2})[/\-.](\d{1,2})(?:[/\-.](\d{2,4}))?(?!\d)", texto or "")
    if not m:
        return None
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
    sem_data = re.sub(r"\d{1,2}[/\-.]\d{1,2}(?:[/\-.]\d{2,4})?", " ", texto or "")
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
