"""Senhas (Argon2) e tokens de sessão assinados."""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from itsdangerous import BadSignature, URLSafeTimedSerializer

from .config import config

_ph = PasswordHasher()
SESSAO_HORAS = 12
SENHA_MINIMO = 10
_COMUNS = {"1234567890", "0123456789", "senha12345", "password123", "qwertyuiop", "admin12345", "mudar12345",
           "abcdefghij", "senhasenha", "1q2w3e4r5t", "password1234", "qwerty12345", "trocar12345", "senha123456"}


def problema_senha(senha: str, login: str | None = None) -> str | None:
    """None se a senha serve; senão, a explicação para a tela. Vale em criar, trocar e redefinir."""
    if len(senha) < SENHA_MINIMO:
        return f"a senha precisa ter ao menos {SENHA_MINIMO} caracteres"
    if senha.isdigit():
        return "a senha não pode ter só números"
    if senha.strip().lower() in _COMUNS:
        return "essa senha é muito comum; escolha outra"
    if login and login.strip() and login.strip().lower() in senha.lower():
        return "a senha não pode conter o login"
    return None


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
