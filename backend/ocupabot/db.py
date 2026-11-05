"""Engine, sessão e base declarativa.

No SQLite cada transação começa com BEGIN IMMEDIATE: a trava de escrita é pega logo no início,
então duas reservas simultâneas não conseguem conferir a mesma vaga ao mesmo tempo.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from sqlalchemy import DateTime, create_engine, event, func
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class ComDatas:
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), onupdate=func.current_timestamp()
    )


def criar_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        caminho = url.split("///", 1)[-1]
        if caminho and caminho != ":memory:":
            Path(caminho).parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(
            url, connect_args={"check_same_thread": False, "timeout": 15}, hide_parameters=True
        )

        @event.listens_for(engine, "connect")
        def _ao_conectar(conn, _):
            conn.isolation_level = None  # o SQLAlchemy controla o BEGIN
            cur = conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA busy_timeout=15000")
            cur.close()

        @event.listens_for(engine, "begin")
        def _ao_iniciar(conn):
            conn.exec_driver_sql("BEGIN IMMEDIATE")

        return engine
    return create_engine(url, pool_pre_ping=True, hide_parameters=True)


_engine: Engine | None = None
_fabrica: sessionmaker[Session] | None = None


def configurar(url: str) -> Engine:
    global _engine, _fabrica
    if _engine is not None:
        _engine.dispose()
    _engine = criar_engine(url)
    _fabrica = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def engine() -> Engine:
    if _engine is None:
        from .config import config

        configurar(config().banco_url)
    assert _engine is not None
    return _engine


def nova_sessao() -> Session:
    engine()
    assert _fabrica is not None
    return _fabrica()


@contextmanager
def sessao() -> Iterator[Session]:
    s = nova_sessao()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()
