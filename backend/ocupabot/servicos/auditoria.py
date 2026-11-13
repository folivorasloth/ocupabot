"""Trilha de auditoria: quem mudou o quê, antes e depois.

Dado pessoal não fica legível na trilha: CPF, RG e nascimento entram mascarados, e CPF ou RG escrito
dentro de texto livre (observação, motivo) sai redigido da foto.
"""

from datetime import date, datetime, time
from enum import Enum
from typing import Any

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from ..dominio.documentos import mascarar_cpf, redigir
from ..modelos import Auditoria
from ..relogio import agora

OCULTOS = {"senha_hash"}
MASCARADOS = {"rg", "nascimento"}
MASCARA = "(informado)"


def _valor(v: Any) -> Any:
    if isinstance(v, Enum):
        return v.value
    if isinstance(v, (datetime, date, time)):
        return v.isoformat()
    if isinstance(v, str):
        return redigir(v)
    return v


def foto(obj: Any) -> dict[str, Any]:
    """Colunas do objeto, com campos sensíveis mascarados."""
    dados = {}
    for col in inspect(obj).mapper.column_attrs:
        v = getattr(obj, col.key)
        if col.key in OCULTOS:
            dados[col.key] = "***" if v else None
        elif col.key == "cpf":
            dados[col.key] = mascarar_cpf(v) or None
        elif col.key in MASCARADOS:
            dados[col.key] = MASCARA if v else None
        else:
            dados[col.key] = _valor(v)
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


def seguranca(s: Session, acao: str, ip: str | None = None, **dados: Any) -> None:
    """Recusa de segurança (login errado, login bloqueado, webhook sem token): grava e fecha a transação,
    porque a rota vai responder com erro e a sessão dela seria desfeita."""
    registrar(s, "seguranca", "-", acao, depois=dados or None, ator="anonimo", ip=ip)
    s.commit()
