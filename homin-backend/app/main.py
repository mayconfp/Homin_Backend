# Arquivo principal da aplicação FastAPI
# Aqui será configurado o app FastAPI, middlewares, CORS, etc.

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes.rag.ai_routes import router as ai_router
from app.routes.auth.auth_routes import router as auth_router
from app.routes.documents.document_routes import router as document_router

# Inicialização do app FastAPI
app = FastAPI(
    title="Homin API",
    description="API para o projeto Homin",
    version="1.0.0"
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:8080"],  # URLs do frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Página inicial simples
@app.get("/")
async def root():
    return {
        "message": "Homin API está funcionando!",
        "docs": "http://127.0.0.1:8000/docs",
        "redoc": "http://127.0.0.1:8000/redoc",
        "auth": {
            "login": "http://127.0.0.1:8000/auth/login",
            "me": "http://127.0.0.1:8000/auth/me"
        }
    }


app.include_router(ai_router)
app.include_router(auth_router)
app.include_router(document_router)


# incluir as rotas aqui


# app.include_router(auth_router)
# app.include_router(document_router)