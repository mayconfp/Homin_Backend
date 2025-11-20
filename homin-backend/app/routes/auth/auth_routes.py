# Rotas de autenticação e autorização
# Endpoints para login, registro, logout, etc.

from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse, JSONResponse
from urllib.parse import quote_plus, unquote_plus, urlparse
import base64

from app.services.auth import (
    get_login_url,
    exchange_code_for_token,
    get_user_info,
)
from app.utils.deps import SessionDep, sync_user_to_local_db, LoggedUserDep, LocalUserDep
import os

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Exemplos de endpoints de autenticação:
# @router.post("/register")
# async def register(user_data: UserCreate):
#     """Endpoint para registro de usuário"""
#     pass

@router.get("/login")
async def login(next: str | None = None):
    """
    Inicia o fluxo de login. O frontend pode passar `next` (ex: `http://localhost:5173`)
    para que, após o callback, o backend redirecione o usuário de volta.

    O valor de `next` é passado via `state` para o provedor (Auth0) e será
    validado no callback antes do redirect final.
    """
    state_value = None
    if next:
        # codifica o retorno para incluir no state (base64 urlsafe)
        encoded = base64.urlsafe_b64encode(next.encode()).decode()
        state_value = quote_plus(encoded)

    url = get_login_url(state=state_value)
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
                "sub": user_info["sub"],
                "permissions": access_payload.get("permissions", [])
            }
            
            # sync_user_to_local_db signature: (token, payload, db_session)
            await sync_user_to_local_db(token_data.get("access_token"), user_payload, db_session)

        # Se o provedor retornou um 'state', tentar decodificar o return URL.
        state = request.query_params.get("state")
        return_to = None
        if state:
            try:
                decoded = unquote_plus(state)
                return_to = base64.urlsafe_b64decode(decoded.encode()).decode()
            except Exception:
                # se falhar, ignora e usa fallback
                return_to = None

        # validação de segurança: allowlist de redirect URIs
        # Permitimos qualquer porta para hosts permitidos (compara por hostname apenas)
        allowed = os.getenv(
            "ALLOWED_REDIRECTS",
            "http://localhost:5173,http://localhost:3000,https://hominsaude.cloud",
        )
        allowed_hosts = set()
        for u in [s.strip() for s in allowed.split(",") if s.strip()]:
            try:
                p = urlparse(u if "://" in u else f"//{u}")
                if p.hostname:
                    allowed_hosts.add(p.hostname.lower())
            except Exception:
                continue

        redirect_target = None
        if return_to:
            try:
                parsed = urlparse(return_to)
                host = parsed.hostname.lower() if parsed.hostname else None
                if host and host in allowed_hosts:
                    redirect_target = return_to
            except Exception:
                redirect_target = None

        if not redirect_target:
            # fallback para variável de ambiente FRONTEND_URL ou default produção
            redirect_target = os.getenv("FRONTEND_URL", "https://www.hominsaude.cloud")

        # Adiciona token na URL de redirect para compatibilidade com front
        # que espera receber ?token=... (ex.: AuthContext lendo query param).
        token = token_data.get("access_token")
        separator = "&" if "?" in redirect_target else "?"
        final_url = f"{redirect_target}{separator}token={token}"

        response = RedirectResponse(url=final_url)

        # Configurar cookie HttpOnly com o access token (backup/segurança)
        secure_flag = os.getenv("ENVIRONMENT") == "production"
        expires = int(token_data.get("expires_in", 3600))

        response.set_cookie(
            key="access_token",
            value=token,
            httponly=True,
            secure=secure_flag,
            samesite="lax",
            max_age=expires,
        )

        return response
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})


@router.get("/logout")
def logout():
    return_to = os.getenv("LOGOUT_RETURN_TO", "http://localhost:8000")
    logout_url = (
        f"https://{os.getenv('AUTH0_DOMAIN')}/v2/logout?"
        f"client_id={os.getenv('AUTH0_CLIENT_ID')}"
        f"&returnTo={return_to}"
    )
    return RedirectResponse(logout_url)


@router.get("/me")
async def get_current_user_info(
    auth_payload: LoggedUserDep,
    local_user: LocalUserDep,
):
    #Endpoint para obter dados do usuário atual.

    #Retorna informação amigável username baseada no usuário local quando disponível
    username = None
    try:
        if getattr(local_user, "nome", None):
            username = local_user.nome
        elif getattr(local_user, "email", None):
            username = local_user.email
    except Exception:
        username = None

    # Fallback para claims caso usuário local não tenha nome
    if not username:
        username = (
            auth_payload.get("name")
            or auth_payload.get("nickname")
            or auth_payload.get("preferred_username")
            or auth_payload.get("email")
            or auth_payload.get("sub")
        )

    return {
        "user": {
            "username": username,
            "email": auth_payload.get("email") or getattr(local_user, "email", None),
            "role": getattr(local_user, "role", None),
            "sub": auth_payload.get("sub"),
        },
        "claims": auth_payload,
    }


# @router.post("/refresh-token")
# async def refresh_token():
#     """Endpoint para renovar token de acesso"""
#     pass