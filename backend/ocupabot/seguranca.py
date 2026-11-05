"""Senhas (Argon2) e tokens de sessão assinados."""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from itsdangerous import BadSignature, URLSafeTimedSerializer

from .config import config

_ph = PasswordHasher()
SESSAO_HORAS = 12


def hash_senha(senha: str) -> str:
    return _ph.hash(senha)


def conferir_senha(hash_: str, senha: str) -> bool:
    try:
        return _ph.verify(hash_, senha)
    except (VerificationError, InvalidHashError):
        return False


def _serializador() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(config().segredo, salt="ocupabot-sessao")


def criar_token(usuario_id: int, versao: int) -> str:
    return _serializador().dumps({"u": usuario_id, "v": versao})


def ler_token(token: str) -> tuple[int, int] | None:
    try:
        dados = _serializador().loads(token, max_age=SESSAO_HORAS * 3600)
        return int(dados["u"]), int(dados["v"])
    except (BadSignature, KeyError, TypeError, ValueError):
        return None
