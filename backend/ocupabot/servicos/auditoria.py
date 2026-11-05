"""Trilha de auditoria: quem mudou o quê, antes e depois."""

from datetime import date, datetime, time
from enum import Enum
from typing import Any

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from ..modelos import Auditoria
from ..relogio import agora

SENSIVEIS = {"senha_hash", "cpf", "rg"}


def _valor(v: Any) -> Any:
    if isinstance(v, Enum):
        return v.value
    if isinstance(v, (datetime, date, time)):
        return v.isoformat()
    return v


def foto(obj: Any) -> dict[str, Any]:
    """Colunas do objeto, com campos sensíveis mascarados."""
    dados = {}
    for col in inspect(obj).mapper.column_attrs:
        v = getattr(obj, col.key)
        dados[col.key] = "***" if (col.key in SENSIVEIS and v) else _valor(v)
    return dados


def registrar(
    s: Session,
    entidade: str,
    entidade_id: Any,
    acao: str,
    antes: dict | None = None,
    depois: dict | None = None,
    usuario_id: int | None = None,
    ator: str = "sistema",
    ip: str | None = None,
) -> None:
    if antes and depois:
        mudou = {k for k in depois if antes.get(k) != depois.get(k)}
        antes = {k: antes.get(k) for k in mudou}
        depois = {k: depois[k] for k in mudou}
    s.add(Auditoria(em=agora(), usuario_id=usuario_id, ator=ator, entidade=entidade,
                    entidade_id=str(entidade_id), acao=acao, antes=antes, depois=depois, ip=ip))
