import time as _t
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...config import config
from ...enums import Perfil
from ...modelos import Usuario
from ...seguranca import SESSAO_HORAS, conferir_senha, criar_token, hash_senha, problema_senha
from ...servicos import auditoria
from ..crud import serializar
from ..deps import COOKIE, admin, ip, qualquer, sessao
from ..esquemas import Login, TrocarSenha, UsuarioAlterar, UsuarioNovo

r = APIRouter(tags=["acesso"])

# Limite de tentativas: 5 por login+IP a cada 5 minutos. A chave junta os dois para que errar a senha
# de alguém (ou uma máquina com vírus) não tranque o login da clínica inteira.
_tentativas: dict[str, deque] = defaultdict(deque)
JANELA, MAXIMO, CHAVES_MAXIMO = 300, 5, 5000
_HASH_FALSO = hash_senha("senha-que-nao-existe")


def _bloqueado(chave: str) -> bool:
    limite = _t.monotonic() - JANELA
    if len(_tentativas) > CHAVES_MAXIMO:  # não cresce sem fim: joga fora o que já venceu
        for k in [k for k, f in _tentativas.items() if not f or f[-1] < limite]:
            del _tentativas[k]
    fila = _tentativas[chave]
    while fila and fila[0] < limite:
        fila.popleft()
    return len(fila) >= MAXIMO


def _cookie(response: Response, u: Usuario) -> None:
    response.set_cookie(COOKIE, criar_token(u.id, u.versao_sessao), httponly=True, samesite="strict",
                        secure=config().cookie_seguro, max_age=SESSAO_HORAS * 3600, path="/")


@r.get("/ambiente", summary="Público: a tela de login avisa quando é ambiente de teste")
def ambiente():
    cfg = config()
    return {"clinica": cfg.nome_clinica, "teste": cfg.modo_teste or cfg.canal != "waha",
            "simulador": cfg.simulador_ativo}


@r.post("/auth/login")
def login(dados: Login, request: Request, response: Response, s: Session = Depends(sessao)):
    nome = dados.login.strip().lower()  # "Maria" e "maria" são a mesma conta
    chave = f"{nome}|{ip(request)}"
    if _bloqueado(chave):
        auditoria.seguranca(s, "login_bloqueado", ip(request), login=nome[:80])
        raise HTTPException(429, "muitas tentativas; espere alguns minutos")
    u = s.scalar(select(Usuario).where(Usuario.login == nome))
    ok = conferir_senha(u.senha_hash if u else _HASH_FALSO, dados.senha)
    if not (u and ok and u.ativo):
        _tentativas[chave].append(_t.monotonic())
        auditoria.seguranca(s, "login_recusado", ip(request), login=nome[:80])
        raise HTTPException(401, "login ou senha incorretos")
    _tentativas.pop(chave, None)
    _cookie(response, u)
    auditoria.registrar(s, "usuario", u.id, "login", usuario_id=u.id, ator="painel", ip=ip(request))
    return serializar(u)  # o token vai só no cookie HttpOnly, nunca no corpo


@r.post("/auth/sair")
def sair(response: Response):
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@r.get("/auth/eu")
def eu(u: Usuario = Depends(qualquer)):
    return serializar(u)


@r.post("/auth/senha", summary="Troca a própria senha (obrigatória no primeiro acesso)")
def trocar_senha(dados: TrocarSenha, request: Request, response: Response, s: Session = Depends(sessao),
                 u: Usuario = Depends(qualquer)):
    if not conferir_senha(u.senha_hash, dados.atual):
        raise HTTPException(403, "a senha atual não confere")
    problema = problema_senha(dados.nova, u.login)
    if problema or dados.nova == dados.atual:
        raise HTTPException(422, problema or "a senha nova precisa ser diferente da atual")
    u.senha_hash = hash_senha(dados.nova)
    u.trocar_senha = False
    u.versao_sessao += 1  # derruba as outras sessões abertas; esta recebe um cookie novo
    _cookie(response, u)
    auditoria.registrar(s, "usuario", u.id, "trocar_senha", usuario_id=u.id, ator="painel", ip=ip(request))
    return serializar(u)


@r.get("/usuarios")
def listar(s: Session = Depends(sessao), _: Usuario = Depends(admin)):
    return [serializar(u) for u in s.scalars(select(Usuario).order_by(Usuario.nome))]


def _gravar(s: Session) -> None:
    try:
        s.flush()
    except IntegrityError as e:
        raise HTTPException(409, "login ou WhatsApp já usado por outro usuário") from e


@r.post("/usuarios", status_code=201)
def criar(dados: UsuarioNovo, request: Request, s: Session = Depends(sessao), u: Usuario = Depends(admin)):
    # a senha foi escolhida pelo admin: a pessoa troca no primeiro acesso
    novo = Usuario(nome=dados.nome, login=dados.login, perfil=dados.perfil, senha_hash=hash_senha(dados.senha),
                   whatsapp=dados.whatsapp, trocar_senha=True)
    s.add(novo)
    _gravar(s)
    auditoria.registrar(s, "usuario", novo.id, "criar", None, auditoria.foto(novo), u.id, "painel", ip(request))
    return serializar(novo)


def _outro_admin_ativo(s: Session, alvo: Usuario) -> bool:
    return bool(s.scalar(select(func.count(Usuario.id)).where(
        Usuario.perfil == Perfil.ADMIN, Usuario.ativo.is_(True), Usuario.id != alvo.id)))


@r.patch("/usuarios/{usuario_id}")
def alterar(usuario_id: int, dados: UsuarioAlterar, request: Request, s: Session = Depends(sessao),
            u: Usuario = Depends(admin)):
    alvo = s.get(Usuario, usuario_id) if usuario_id < 2**63 else None
    if alvo is None:
        raise HTTPException(404, "não encontrado")
    antes = auditoria.foto(alvo)
    deixa_de_ser_admin = alvo.perfil == Perfil.ADMIN and alvo.ativo and (
        dados.ativo is False or (dados.perfil is not None and dados.perfil != Perfil.ADMIN))
    if deixa_de_ser_admin and not _outro_admin_ativo(s, alvo):
        raise HTTPException(409, "este é o único administrador ativo: crie outro antes de mudar este")
    if dados.nome is not None:
        alvo.nome = dados.nome
    if dados.perfil is not None:
        alvo.perfil = dados.perfil
    if dados.ativo is not None:
        alvo.ativo = dados.ativo
    if "whatsapp" in dados.model_fields_set:
        alvo.whatsapp = dados.whatsapp
    if dados.senha:
        if alvo.id == u.id:
            raise HTTPException(422, "para trocar a sua própria senha use 'Trocar senha' no menu da conta")
        problema = problema_senha(dados.senha, alvo.login)
        if problema:
            raise HTTPException(422, problema)
        alvo.senha_hash = hash_senha(dados.senha)
        alvo.trocar_senha = True
    if dados.senha or dados.ativo is False or dados.perfil is not None:
        alvo.versao_sessao += 1  # derruba as sessões abertas
    _gravar(s)
    auditoria.registrar(s, "usuario", alvo.id, "alterar", antes, auditoria.foto(alvo), u.id, "painel", ip(request))
    return serializar(alvo)
