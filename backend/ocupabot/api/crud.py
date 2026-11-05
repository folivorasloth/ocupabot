"""Gera rotas de cadastro (listar, ler, criar, alterar e, opcionalmente, excluir) com auditoria."""

from __future__ import annotations

from datetime import date, datetime, time
from enum import Enum
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..dominio.documentos import mascarar_cpf, so_digitos
from ..enums import Perfil
from ..modelos import Usuario
from ..servicos import auditoria
from .deps import ip, qualquer, sessao

PROTEGIDOS = {"id", "criado_em", "atualizado_em", "senha_hash", "versao_sessao"}


def serializar(obj: Any, perfil: Perfil | None = None) -> dict[str, Any]:
    dados: dict[str, Any] = {}
    for col in inspect(obj).mapper.column_attrs:
        v = getattr(obj, col.key)
        if col.key == "senha_hash":
            continue
        if col.key == "cpf":
            v = mascarar_cpf(v)
        elif col.key in {"rg", "nascimento", "telefone", "rh_telefone"} and perfil == Perfil.LEITURA and v:
            v = "***"
        elif isinstance(v, Enum):
            v = v.value
        elif isinstance(v, (date, datetime, time)):
            v = v.isoformat()
        dados[col.key] = v
    return dados


def _converter(modelo: type, dados: dict[str, Any]) -> dict[str, Any]:
    colunas = {c.key: c for c in inspect(modelo).mapper.column_attrs}
    saida = {}
    for chave, valor in dados.items():
        if chave in PROTEGIDOS or chave not in colunas:
            raise HTTPException(422, f"campo inválido: {chave}")
        tipo = colunas[chave].columns[0].type
        py = getattr(tipo, "python_type", None) if not hasattr(tipo, "enums") else None
        if valor is not None and py is not None:
            try:
                if py is date and isinstance(valor, str):
                    valor = date.fromisoformat(valor)
                elif py is time and isinstance(valor, str):
                    valor = time.fromisoformat(valor)
                elif py is bool and not isinstance(valor, bool):
                    raise ValueError
                elif py is int and not isinstance(valor, int):
                    valor = int(valor)
            except (ValueError, TypeError) as e:
                raise HTTPException(422, f"valor inválido para {chave}") from e
        if chave in {"cpf", "cnpj"} and valor:
            valor = so_digitos(valor)
        saida[chave] = valor
    return saida


def rotas_crud(
    modelo: type,
    prefixo: str,
    nome: str,
    escrever: Any,
    excluir: bool = False,
    ordem: Any = None,
    busca: list[str] | None = None,
) -> APIRouter:
    r = APIRouter(prefix=prefixo, tags=[nome])
    chave_pk = inspect(modelo).primary_key[0].key

    @r.get("", summary=f"Listar {nome}")
    def listar(q: str | None = None, limite: int = 500, s: Session = Depends(sessao),
               u: Usuario = Depends(qualquer)):
        consulta = select(modelo)
        if q and busca:
            from sqlalchemy import or_

            consulta = consulta.where(or_(*[getattr(modelo, c).ilike(f"%{q}%") for c in busca]))
        consulta = consulta.order_by(ordem if ordem is not None else getattr(modelo, chave_pk))
        return [serializar(o, u.perfil) for o in s.scalars(consulta.limit(min(limite, 2000)))]

    @r.get("/{item_id}", summary=f"Ler {nome}")
    def ler(item_id: str, s: Session = Depends(sessao), u: Usuario = Depends(qualquer)):
        obj = s.get(modelo, int(item_id) if item_id.isdigit() and chave_pk == "id" else item_id)
        if obj is None:
            raise HTTPException(404, "não encontrado")
        return serializar(obj, u.perfil)

    @r.post("", summary=f"Criar {nome}", status_code=201)
    def criar(request: Request, dados: dict[str, Any] = Body(...), s: Session = Depends(sessao),
              u: Usuario = Depends(escrever)):
        obj = modelo(**_converter(modelo, dados))
        s.add(obj)
        try:
            s.flush()
        except IntegrityError as e:
            raise HTTPException(409, "registro duplicado ou referência inválida") from e
        auditoria.registrar(s, nome, getattr(obj, chave_pk), "criar", None, auditoria.foto(obj), u.id,
                            "painel", ip(request))
        return serializar(obj, u.perfil)

    @r.patch("/{item_id}", summary=f"Alterar {nome}")
    def alterar(item_id: str, request: Request, dados: dict[str, Any] = Body(...),
                s: Session = Depends(sessao), u: Usuario = Depends(escrever)):
        obj = s.get(modelo, int(item_id) if item_id.isdigit() and chave_pk == "id" else item_id)
        if obj is None:
            raise HTTPException(404, "não encontrado")
        antes = auditoria.foto(obj)
        for k, v in _converter(modelo, dados).items():
            setattr(obj, k, v)
        try:
            s.flush()
        except IntegrityError as e:
            raise HTTPException(409, "registro duplicado ou referência inválida") from e
        auditoria.registrar(s, nome, item_id, "alterar", antes, auditoria.foto(obj), u.id, "painel", ip(request))
        return serializar(obj, u.perfil)

    if excluir:

        @r.delete("/{item_id}", summary=f"Excluir {nome}", status_code=204)
        def apagar(item_id: int, request: Request, s: Session = Depends(sessao), u: Usuario = Depends(escrever)):
            obj = s.get(modelo, item_id)
            if obj is None:
                raise HTTPException(404, "não encontrado")
            antes = auditoria.foto(obj)
            s.delete(obj)
            s.flush()
            auditoria.registrar(s, nome, item_id, "excluir", antes, None, u.id, "painel", ip(request))

    return r
