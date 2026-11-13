"""Linha de comando: migrar banco, criar usuário, carregar demonstração e conversar com o bot.

    python -m ocupabot.cli migrar
    python -m ocupabot.cli usuario --login admin --nome Admin --perfil ADMIN
    python -m ocupabot.cli demo
    python -m ocupabot.cli conversar --telefone 5500000000001
"""

from __future__ import annotations

import argparse
import getpass
from pathlib import Path

from alembic import command
from alembic.config import Config as AlembicConfig

from . import db
from .enums import Perfil
from .modelos import Usuario
from .seeds import demonstracao, essenciais
from .seguranca import SENHA_MINIMO, hash_senha, problema_senha
from .servicos import auditoria


def _raiz() -> Path:
    """Pasta com alembic.ini: a do código-fonte ou, instalado como pacote, a pasta atual."""
    fonte = Path(__file__).resolve().parent.parent
    return fonte if (fonte / "alembic.ini").exists() else Path.cwd()


RAIZ = _raiz()


def migrar() -> None:
    cfg = AlembicConfig(str(RAIZ / "alembic.ini"))
    cfg.set_main_option("script_location", str(RAIZ / "migracoes"))
    command.upgrade(cfg, "head")
    with db.sessao() as s:
        essenciais(s)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="ocupabot")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("migrar", help="aplica as migrations e os dados essenciais")
    u = sub.add_parser("usuario", help="cria um usuário do painel")
    u.add_argument("--login", required=True)
    u.add_argument("--nome", required=True)
    u.add_argument("--perfil", choices=[x.value for x in Perfil], required=True)
    d = sub.add_parser("demo", help="carrega dados fictícios de demonstração")
    d.add_argument("--senha", default="ocupabot-demo", help="senha de todos os usuários de demonstração")
    c = sub.add_parser("conversar", help="conversa com o bot no terminal")
    c.add_argument("--telefone", default="5500000000001")
    a = p.parse_args(argv)

    if a.cmd == "migrar":
        migrar()
        print("banco atualizado")
    elif a.cmd == "usuario":
        login = a.login.strip().lower()  # "Maria" e "maria" seriam duas contas quase iguais
        senha = getpass.getpass(f"senha (mín. {SENHA_MINIMO}): ")
        problema = problema_senha(senha, login)  # a mesma regra do painel
        if not login or problema:
            raise SystemExit(problema or "login vazio")
        if senha != getpass.getpass("repita a senha: "):
            raise SystemExit("as senhas não conferem")
        with db.sessao() as s:
            if s.query(Usuario).filter(Usuario.login == login).first():
                raise SystemExit("login já existe")
            u = Usuario(login=login, nome=a.nome, perfil=Perfil(a.perfil), senha_hash=hash_senha(senha))
            s.add(u)
            s.flush()
            auditoria.registrar(s, "usuario", u.id, "criar", None, auditoria.foto(u), ator="linha_de_comando")
        print("usuário criado")
    elif a.cmd == "demo":
        migrar()
        with db.sessao() as s:
            demonstracao(s, a.senha)
        print("demonstração carregada: logins admin, supervisao, recepcao")
    elif a.cmd == "conversar":
        from .bot.maquina import processar

        migrar()
        print("Digite as mensagens (Ctrl+C para sair).")
        while True:
            try:
                texto = input("você> ")
            except (EOFError, KeyboardInterrupt):
                break
            with db.sessao() as s:
                for resposta in processar(s, a.telefone, texto, simulado=True):
                    print("bot>", resposta.replace("\n", "\n     "))


if __name__ == "__main__":
    main()
