# Configurações do banco de dados SQLAlchemy
# Conexão com PostgreSQL usando as configurações do config.py

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from ..config import settings

# Criar engine do SQLAlchemy usando a DATABASE_URL do .env
engine = create_engine(
    settings.database_url,
    # Para PostgreSQL, adicionar configurações de pool se necessário
    pool_pre_ping=True,  # Verifica conexão antes de usar
    echo=False  # True para debug SQL, False para produção
)

# Criar SessionLocal para gerenciar sessões do banco
SessionLocal = sessionmaker(
    autocommit=False, 
    autoflush=False, 
    bind=engine
)

# Base para os modelos SQLAlchemy
Base = declarative_base()

# Dependência para obter sessão do banco (usar no FastAPI)
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
    Base.metadata.create_all(bind=engine)