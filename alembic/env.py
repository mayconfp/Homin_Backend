from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import sys
import os

# Adicionar o diretório do projeto ao path
projeto_path = os.path.join(os.path.dirname(__file__), '..', 'homin-backend')
sys.path.insert(0, projeto_path)

# Importar Base e models
from app.database.config import Base
import app.database.models  # Garantir que os models sejam importados

# Alembic Config object
config = context.config

# Setup logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# MetaData para autogeração de migrações    
target_metadata = Base.metadata


# Função para executar migrações offline

def run_migrations_offline() -> None:

    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

# migracao online
def run_migrations_online() -> None:

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
