# Rotas de autenticação e autorização
# Endpoints para login, registro, logout, etc.

from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse, JSONResponse
from app.services.auth import (
    get_login_url,
    exchange_code_for_token,
    get_user_info,
    sync_user_to_local_db,
    LoggedUserDep
)
from app.utils.deps import SessionDep
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
async def callback(request: Request, db_session: SessionDep, code: str = None):
    if not code:
        return JSONResponse(status_code=400, content={"error": "Código de autorização ausente"})

    try:
        token_data = exchange_code_for_token(code)
        user_info = get_user_info(token_data["access_token"])

        # Sincronizar usuário com base local usando dados completos do userinfo
        if user_info.get("email"):
            # Criar payload com dados do userinfo + permissões do access_token
            from app.utils.deps import verify_jwt
            access_payload = verify_jwt(token_data["access_token"])
            
            user_payload = {
                "email": user_info["email"],
                "name": user_info.get("name", user_info.get("email")),
                "sub": user_info["sub"],  # ← ADICIONADO: incluir sub do userinfo
                "permissions": access_payload.get("permissions", [])
            }
            
            await sync_user_to_local_db(user_payload, db_session)

        return JSONResponse(
            content={
                "message": "Login bem-sucedido!",
                "user": user_info,
                "tokens": token_data,
                "sync_info": {
                    "email": user_info.get("email"),
                    "permissions": verify_jwt(token_data["access_token"]).get("permissions", [])
                }
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


@router.get("/me")
async def get_current_user_info(user: LoggedUserDep):
    """Endpoint para obter dados do usuário atual"""
    return {
        "user": user,
        "message": "Dados do usuário atual"
    }


# @router.post("/refresh-token")
# async def refresh_token():
#     """Endpoint para renovar token de acesso"""
#     pass