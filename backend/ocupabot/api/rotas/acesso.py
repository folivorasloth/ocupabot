import time as _t
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...config import config
from ...modelos import Usuario
from ...seguranca import SESSAO_HORAS, conferir_senha, criar_token, hash_senha
from ...servicos import auditoria
from ..crud import serializar
from ..deps import COOKIE, admin, ip, qualquer, sessao
from ..esquemas import Login, UsuarioAlterar, UsuarioNovo

r = APIRouter(tags=["acesso"])

# Limite de tentativas: 5 por login+IP a cada 5 minutos
_tentativas: dict[str, deque] = defaultdict(deque)
JANELA, MAXIMO = 300, 5
_HASH_FALSO = hash_senha("senha-que-nao-existe")


def _bloqueado(chave: str) -> bool:
    fila = _tentativas[chave]
    limite = _t.monotonic() - JANELA
    while fila and fila[0] < limite:
        fila.popleft()
    return len(fila) >= MAXIMO


@r.post("/auth/login")
def login(dados: Login, request: Request, response: Response, s: Session = Depends(sessao)):
    chave = f"{dados.login.lower()}|{ip(request)}"
    if _bloqueado(chave):
        raise HTTPException(429, "muitas tentativas; espere alguns minutos")
    u = s.scalar(select(Usuario).where(Usuario.login == dados.login.lower()))
    ok = conferir_senha(u.senha_hash if u else _HASH_FALSO, dados.senha)
    if not (u and ok and u.ativo):
        _tentativas[chave].append(_t.monotonic())
        raise HTTPException(401, "login ou senha incorretos")
    _tentativas.pop(chave, None)
    response.set_cookie(COOKIE, criar_token(u.id, u.versao_sessao), httponly=True, samesite="strict",
                        secure=config().cookie_seguro, max_age=SESSAO_HORAS * 3600, path="/")
    auditoria.registrar(s, "usuario", u.id, "login", usuario_id=u.id, ator="painel", ip=ip(request))
    return serializar(u)


@r.post("/auth/sair")
def sair(response: Response):
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@r.get("/auth/eu")
def eu(u: Usuario = Depends(qualquer)):
    return serializar(u)


@r.get("/usuarios")
def listar(s: Session = Depends(sessao), _: Usuario = Depends(admin)):
    return [serializar(u) for u in s.scalars(select(Usuario).order_by(Usuario.nome))]


@r.post("/usuarios", status_code=201)
def criar(dados: UsuarioNovo, request: Request, s: Session = Depends(sessao), u: Usuario = Depends(admin)):
    novo = Usuario(nome=dados.nome, login=dados.login, perfil=dados.perfil, senha_hash=hash_senha(dados.senha))
    s.add(novo)
    try:
        s.flush()
    except IntegrityError as e:
        raise HTTPException(409, "login já existe") from e
    auditoria.registrar(s, "usuario", novo.id, "criar", None, auditoria.foto(novo), u.id, "painel", ip(request))
    return serializar(novo)


@r.patch("/usuarios/{usuario_id}")
def alterar(usuario_id: int, dados: UsuarioAlterar, request: Request, s: Session = Depends(sessao),
            u: Usuario = Depends(admin)):
    alvo = s.get(Usuario, usuario_id)
    if alvo is None:
        raise HTTPException(404, "não encontrado")
    antes = auditoria.foto(alvo)
    if dados.nome is not None:
        alvo.nome = dados.nome
    if dados.perfil is not None:
        alvo.perfil = dados.perfil
    if dados.ativo is not None:
        alvo.ativo = dados.ativo
    if dados.senha:
        alvo.senha_hash = hash_senha(dados.senha)
    if dados.senha or dados.ativo is False or dados.perfil is not None:
        alvo.versao_sessao += 1  # derruba as sessões abertas
    auditoria.registrar(s, "usuario", alvo.id, "alterar", antes, auditoria.foto(alvo), u.id, "painel", ip(request))
    return serializar(alvo)
