# Rotas de autenticação e autorização
# Endpoints para login, registro, logout, etc.

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, JSONResponse
from app.services.auth import (
    get_login_url,
    exchange_code_for_token,
    get_user_info
)
import os

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Exemplos de endpoints de autenticação:
# @router.post("/register")
# async def register(user_data: UserCreate):
#     """Endpoint para registro de usuário"""
#     pass

@router.get("/login")
async def login():
    url = get_login_url()
    return RedirectResponse(url=url)


@router.get("/callback")
async def callback(request: Request, code: str = None):
    if not code:
        return JSONResponse(status_code=400, content={"error": "Código de autorização ausente"})

    try:
        token_data = exchange_code_for_token(code)
        user_info = get_user_info(token_data["access_token"])

        # Aqui você pode salvar o usuário no banco, criar sessão JWT etc.
        return JSONResponse(
            content={
                "message": "Login bem-sucedido!",
                "user": user_info,
                "tokens": token_data
            }
        )
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})


@router.get("/logout")
async def logout():
    logout_url = (
        f"https://{os.getenv('AUTH0_DOMAIN')}/v2/logout?"
        f"client_id={os.getenv('AUTH0_CLIENT_ID')}"
        f"&returnTo=http://localhost:8000"
    )
    return RedirectResponse(url=logout_url)

# @router.get("/me")
# async def get_current_user():
#     """Endpoint para obter dados do usuário atual"""
#     pass

# @router.post("/refresh-token")
# async def refresh_token():
#     """Endpoint para renovar token de acesso"""
#     pass