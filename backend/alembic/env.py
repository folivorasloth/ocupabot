from alembic import context
from ocupabot import db, modelos  # noqa: F401 - registra as tabelas
from ocupabot.config import config

alvo = db.Base.metadata


def rodar() -> None:
    engine = db.criar_engine(context.config.get_main_option("sqlalchemy.url") or config().banco_url)
    with engine.connect() as conexao:
        context.configure(connection=conexao, target_metadata=alvo, render_as_batch=True,
                          compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


rodar()
