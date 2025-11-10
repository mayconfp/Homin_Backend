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
        f"&audience={AUTH0_AUDIENCE}"  # para quais servico o token e valido
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

def get_user_permissions_from_auth0(access_token: str):
    """Obtém as permissões/roles do usuário do Auth0"""
    try:
        # Buscar permissões do usuário via Management API
        userinfo_url = f"https://{AUTH0_DOMAIN}/userinfo"
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(userinfo_url, headers=headers)
        
        if response.status_code == 200:
            user_info = response.json()
            
            # As permissões podem estar em diferentes lugares dependendo da configuração
            permissions = []
            roles = []
            
            # Verificar se há permissões no token customizado
            if 'permissions' in user_info:
                permissions = user_info.get('permissions', [])
            
            if 'https://homin.app/roles' in user_info:
                roles = user_info.get('https://homin.app/roles', [])
            elif 'roles' in user_info:
                roles = user_info.get('roles', [])
            
            # Determinar role baseado nas permissões
            if 'admin:documents' in permissions or 'admin' in roles:
                return 'admin'
            elif 'chat:access' in permissions or any('user' in str(r).lower() for r in roles):
                return 'user'
            else:
                return 'user'  # default
                
    except Exception as e:
        print(f"⚠️ Erro ao obter permissões do Auth0: {e}")
    
    return 'user'  # fallback


async def sync_user_to_local_db(payload: Dict, db_session: SessionDep, access_token: str = None) -> None:
    """Sincroniza usuário do Auth0 para a base local (não bloqueia se der erro)"""
    try:
        # Extrair dados essenciais
        email = payload.get("email")
        nome = payload.get("name", payload.get("given_name", ""))
        auth0_sub = payload.get("sub")
        permissions = payload.get("permissions", [])
        
        if not auth0_sub:
            print(f"⚠️ Sub ausente - não é possível sincronizar. Payload: {payload}")
            return
        
        # Determinar role baseado nas permissões
        user_role = 'user'  # default
        if 'admin:documents' in permissions:
            user_role = 'admin'
        
        # Buscar usuário por auth0_sub (sempre disponível) ou email (se presente)
        if email:
            stmt = select(Usuario).where(
                (Usuario.email == email) | (Usuario.auth0_sub == auth0_sub)
            )
        else:
            stmt = select(Usuario).where(Usuario.auth0_sub == auth0_sub)
        
        user = await db_session.scalar(stmt)
        
        if not user:
            # Se não tem email (JWT), não criar usuário - só no callback
            if not email:
                print(f"ℹ️ Usuário {auth0_sub} não encontrado na base local. Aguardando callback com email.")
                return
                
            # Primeira vez: criar usuário (só no callback quando tem email)
            user = Usuario(
                email=email,
                nome=nome or email,
                auth0_sub=auth0_sub,
                role=user_role
            )
            db_session.add(user)
            await db_session.commit()
            print(f"✅ Novo usuário criado: {email} (role: {user_role}, sub: {auth0_sub})")
        else:
            # Atualizar dados se mudaram
            updated = False
            
            # Atualizar email/nome apenas se vieram no payload (callback)
            if email and user.email != email:
                user.email = email
                updated = True
                
            if nome and user.nome != nome:
                user.nome = nome
                updated = True
                
            # Atualizar auth0_sub se necessário
            if user.auth0_sub != auth0_sub:
                user.auth0_sub = auth0_sub
                updated = True
                
            # Sempre atualizar role baseado nas permissions atuais
            if user.role != user_role:
                old_role = user.role
                user.role = user_role
                updated = True
                print(f"✅ Role atualizado para {user.email or auth0_sub}: {old_role} -> {user_role}")
            
            if updated:
                await db_session.commit()
                print(f"✅ Usuário atualizado: {user.email or auth0_sub}")
                
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
    # Usar o próprio token JWT como access_token para buscar permissões
    await sync_user_to_local_db(payload, db_session, access_token=token)
    
    return payload


# Tipo de dependência injection
LoggedUserDep = Annotated[Dict, Depends(get_current_user)]


def require_permission(permission: Permissions):
    """Factory para criar dependency que valida uma permissão específica"""
    async def check_permission(user: LoggedUserDep):
        from app.utils.permission_utils import validate_permission
        await validate_permission(user, permission)
        return user
    return check_permission
