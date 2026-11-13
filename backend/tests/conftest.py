from datetime import datetime

import pytest

from ocupabot import db, relogio
from ocupabot.api.rotas import acesso
from ocupabot.config import config
from ocupabot.db import Base
from ocupabot.integracoes.mensageria import CanalConsole, definir_canal
from ocupabot.seeds import demonstracao

AGORA = datetime(2026, 11, 5, 9, 0)  # quinta-feira, dentro do expediente


@pytest.fixture(autouse=True)
def ambiente(tmp_path, monkeypatch):
    monkeypatch.setenv("OCUPABOT_SEGREDO", "teste")
    monkeypatch.setenv("OCUPABOT_MODO_TESTE", "false")
    monkeypatch.setenv("OCUPABOT_AGENDA_EXTERNA", "nenhum")
    monkeypatch.setenv("OCUPABOT_SIMULADOR_ATIVO", "true")
    monkeypatch.setenv("OCUPABOT_BOT_ATIVO", "true")
    monkeypatch.setenv("OCUPABOT_WEBHOOK_TOKEN", "token-teste")
    config.cache_clear()
    engine = db.configurar(f"sqlite:///{tmp_path}/teste.db")
    Base.metadata.create_all(engine)
    with db.sessao() as s:
        demonstracao(s, senha_admin="senha-teste")
    relogio.fixar(AGORA)
    acesso._tentativas.clear()  # o limite de login fica em memória: um teste não bloqueia o outro
    canal = CanalConsole()
    definir_canal(canal)
    yield canal
    relogio.fixar(None)
    definir_canal(None)
    config.cache_clear()


@pytest.fixture
def s():
    sessao = db.nova_sessao()
    yield sessao
    sessao.rollback()
    sessao.close()
