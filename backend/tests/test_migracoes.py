from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext

from ocupabot import db
from ocupabot.cli import RAIZ


def test_migrations_batem_com_os_modelos(tmp_path):
    url = f"sqlite:///{tmp_path}/mig.db"
    cfg = Config(str(RAIZ / "alembic.ini"))
    cfg.set_main_option("script_location", str(RAIZ / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
    engine = db.criar_engine(url)
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn, opts={"compare_type": True}), db.Base.metadata)
    assert diff == []
