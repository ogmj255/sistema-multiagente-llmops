from logging.config import fileConfig

from alembic import context
from app.db.database import Base, engine
from app.db.models import AnalysisRun

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Garantiza que el modelo quede registrado en la metadata.
_ = AnalysisRun


def run_migrations_offline() -> None:
    """Ejecuta migraciones sin abrir una conexión a PostgreSQL."""

    context.configure(
        url=engine.url.render_as_string(
            hide_password=False
        ),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={
            "paramstyle": "named",
        },
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Ejecuta migraciones usando la conexión configurada."""

    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=False,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
