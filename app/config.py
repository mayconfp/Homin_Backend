

from pydantic import BaseSettings

class Settings(BaseSettings):
    # Configurações do banco de dados PostgreSQL
    database_url: str
    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str
    db_password: str
    
    # Configurações de IA
    openai_api_key: str
    
    # ChromaDB (banco de vetores para IA)
    chroma_db_path: str = "./banco_de_dados"

    # Configurações de segurança (para autenticação JWT)
    secret_key: str = "dev-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # CORS
    cors_origins: list = ["http://localhost:3000", "http://localhost:8000"]

    class Config:
        env_file = ".env"

settings = Settings()