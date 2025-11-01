# Arquivo principal da aplicação FastAPI
# Aqui será configurado o app FastAPI, middlewares, CORS, etc.

from fastapi import FastAPI

# Inicialização do app FastAPI
app = FastAPI(
    title="Homin API",
    description="API para o projeto Homin",
    version="1.0.0"
)

# Exemplo de rota básica
@app.get("/")
async def root():
    return {"message": "Homin API está funcionando"}
from app.routes.rag.ai_routes import router as ai_router

app.include_router(ai_router)

# Importar e incluir as rotas aqui
# from routes.auth_routes import router as auth_router
# from routes.ai_routes import router as ai_router
# from routes.document_routes import router as document_router

# app.include_router(auth_router)
# app.include_router(document_router)