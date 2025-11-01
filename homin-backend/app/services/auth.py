import os
import json
import requests
from fastapi import Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt
from dotenv import load_dotenv
from typing import Dict, List, Annotated
from app.core.permissions import Permissions
from app.utils.permission_utils import validate_permission

load_dotenv()

AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
AUTH0_CLIENT_ID = os.getenv("AUTH0_CLIENT_ID")
AUTH0_CLIENT_SECRET = os.getenv("AUTH0_CLIENT_SECRET")
AUTH0_CALLBACK_URL = os.getenv("AUTH0_CALLBACK_URL")
AUTH0_AUDIENCE = os.getenv("AUTH0_AUDIENCE")

# Segurança
security = HTTPBearer()


def get_login_url():
    """Gera a URL de login do Auth0 (com Google)"""
    return (
        f"https://{AUTH0_DOMAIN}/authorize"
        f"?response_type=code"
        f"&client_id={AUTH0_CLIENT_ID}"
        f"&redirect_uri={AUTH0_CALLBACK_URL}"
        f"&scope=openid profile email"
        f"&audience={AUTH0_AUDIENCE}"
        f"&connection=google-oauth2"
    )


def exchange_code_for_token(code: str):
    """Troca o código de autorização por tokens"""
    token_url = f"https://{AUTH0_DOMAIN}/oauth/token"
    payload = {
        "grant_type": "authorization_code",
        "client_id": AUTH0_CLIENT_ID,
        "client_secret": AUTH0_CLIENT_SECRET,
        "code": code,
        "redirect_uri": AUTH0_CALLBACK_URL,
    }

    response = requests.post(token_url, json=payload)
    if response.status_code != 200:
        raise HTTPException(status_code=400, detail="Erro ao obter token do Auth0")

    return response.json()


def get_user_info(access_token: str):
    """Obtém informações do usuário logado"""
    userinfo_url = f"https://{AUTH0_DOMAIN}/userinfo"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(userinfo_url, headers=headers)

    if response.status_code != 200:
        raise HTTPException(status_code=400, detail="Erro ao obter informações do usuário")

    return response.json()


def verify_jwt(token: str):
    """Verifica e decodifica um JWT emitido pelo Auth0"""
    try:
        header = jwt.get_unverified_header(token)
        jwks_url = f"https://{AUTH0_DOMAIN}/.well-known/jwks.json"
        jwks = requests.get(jwks_url).json()
        rsa_key = {}

        for key in jwks["keys"]:
            if key["kid"] == header["kid"]:
                rsa_key = {
                    "kty": key["kty"],
                    "kid": key["kid"],
                    "use": key["use"],
                    "n": key["n"],
                    "e": key["e"],
                }
        if rsa_key:
            payload = jwt.decode(
                token,
                rsa_key,
                algorithms=["RS256"],
                audience=AUTH0_AUDIENCE,
                issuer=f"https://{AUTH0_DOMAIN}/"
            )
            return payload
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Token inválido: {str(e)}")


# ========== DEPENDÊNCIAS PARA PROTEÇÃO DE ROTAS ==========

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict:
    """Obtém o usuário atual validando o JWT"""
    token = credentials.credentials
    payload = verify_jwt(token)
    return payload


# Tipo de dependencia injection 
LoggedUserDep = Annotated[Dict, Depends(get_current_user)]


def require_permission_new(permission: Permissions):

# para criar dependency que valida múltiplas permissões
    async def check_permission(user: LoggedUserDep):
        await validate_permission(user, permission)
        return user
    return check_permission
