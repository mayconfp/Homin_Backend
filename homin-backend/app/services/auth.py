import os
import json
import requests
from fastapi import Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt
from dotenv import load_dotenv
from typing import Dict, List, Annotated
from sqlalchemy import select
from app.core.permissions import Permissions
from app.database.models import Usuario
from app.utils.deps import SessionDep, verify_jwt

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


# ========== DEPENDÊNCIAS PARA PROTEÇÃO DE ROTAS ==========

async def sync_user_to_local_db(payload: Dict, db_session: SessionDep) -> None:
    """Sincroniza usuário do Auth0 para a base local (não bloqueia se der erro)"""
    try:
        email = payload.get("email")
        nome = payload.get("name", email)
        
        if not email:
            return  # Skip se não tiver email
        
        # Buscar usuário na base local
        stmt = select(Usuario).where(Usuario.email == email)
        user = await db_session.scalar(stmt)
        
        if not user:
            # Primeira vez: criar usuário com permissão básica
            user = Usuario(
                email=email,
                nome=nome,
                role="user"  # Por padrão: apenas CHAT_ACCESS
            )
            db_session.add(user)
            await db_session.commit()
            print(f"✅ Novo usuário criado na base local: {email}")
        else:
            # Atualizar nome se mudou
            if user.nome != nome:
                user.nome = nome
                await db_session.commit()
    except Exception as e:
        print(f"⚠️ Erro ao sincronizar usuário na base local: {e}")
        # Não falha - continua com auth normal


async def get_current_user(
    db_session: SessionDep,
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Dict:
    """Obtém o usuário atual validando o JWT + sincroniza na base local"""
    token = credentials.credentials
    payload = verify_jwt(token)
    
    # Sincronizar com base local (em background, sem bloquear)
    await sync_user_to_local_db(payload, db_session)
    
    return payload


# Tipo de dependência injection
LoggedUserDep = Annotated[Dict, Depends(get_current_user)]


def require_permission_new(permission: Permissions):
    # para criar dependency que valida múltiplas permissões
    async def check_permission(user: LoggedUserDep):
        from app.utils.permission_utils import validate_permission
        await validate_permission(user, permission)
        return user
    return check_permission
