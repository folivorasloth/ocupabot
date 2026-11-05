"""Dependências comuns das rotas: sessão do banco, usuário logado e perfis."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from .. import db
from ..enums import Perfil
from ..modelos import Usuario
from ..seguranca import ler_token

COOKIE = "ocupabot_sessao"


def sessao() -> Iterator[Session]:
    s = db.nova_sessao()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def usuario_atual(request: Request, s: Session = Depends(sessao)) -> Usuario:
    token = request.cookies.get(COOKIE)
    dados = ler_token(token) if token else None
    if dados is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "faça login")
    u = s.get(Usuario, dados[0])
    if u is None or not u.ativo or u.versao_sessao != dados[1]:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "sessão expirada")
    return u


def exige(*perfis: Perfil):
    permitidos = set(perfis) | {Perfil.ADMIN}

    def _dep(u: Usuario = Depends(usuario_atual)) -> Usuario:
        if u.perfil not in permitidos:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "seu perfil não permite esta ação")
        return u

    return _dep


EQUIPE = (Perfil.SUPERVISAO, Perfil.RECEPCAO)
qualquer = usuario_atual
equipe = exige(*EQUIPE)
admin = exige()


def ip(request: Request) -> str | None:
    return request.client.host if request.client else None
