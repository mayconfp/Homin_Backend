# Configurações do banco de dados SQLAlchemy
# Conexão com PostgreSQL usando as configurações do config.py

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from ..config import settings

# Criar engine async do SQLAlchemy usando a DATABASE_URL do .env
async_engine = create_async_engine(
    settings.database_url.replace("postgresql://", "postgresql+asyncpg://"),
    # Para PostgreSQL, adicionar configurações de pool se necessário
    pool_pre_ping=True,  # Verifica conexão antes de usar
    echo=False  # True para debug SQL, False para produção
)

# Criar engine síncrono para migrações do Alembic
sync_engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    echo=False
)

# Criar SessionLocal async para gerenciar sessões do banco
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Criar SessionLocal síncrono para compatibilidade (se precisar)
SessionLocal = sessionmaker(
    autocommit=False, 
    autoflush=False, 
    bind=sync_engine
)

# Base para os modelos SQLAlchemy
Base = declarative_base()

# Dependência async para obter sessão do banco (usar no FastAPI)
async def get_async_db():
    """
    Dependência do FastAPI para obter sessão async do banco.
    Uso: def endpoint(db: AsyncSession = Depends(get_async_db)):
    """
    async with AsyncSessionLocal() as session:
        yield session

# Dependência síncrona para obter sessão do banco (compatibilidade)
def get_db():
    """
    Dependência do FastAPI para obter sessão do banco.
    Uso: def endpoint(db: Session = Depends(get_db)):
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Função para criar todas as tabelas
def create_tables():
    """
    Cria todas as tabelas no banco de dados.
    Chamar uma vez quando inicializar a aplicação.
    """
    Base.metadata.create_all(bind=sync_engine)