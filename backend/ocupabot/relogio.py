"""Relógio único do sistema, no fuso da clínica. Os testes podem fixar a hora com `fixar()`."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

FUSO = ZoneInfo("America/Sao_Paulo")
_fixo: datetime | None = None


def agora() -> datetime:
    """Hora local da clínica, sem fuso (naive), como é gravada no banco."""
    if _fixo is not None:
        return _fixo
    return datetime.now(FUSO).replace(tzinfo=None, microsecond=0)


def hoje() -> date:
    return agora().date()


def fixar(momento: datetime | None) -> None:
    global _fixo
    _fixo = momento
