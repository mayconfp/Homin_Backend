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

# Segurança (a verificação de token e sincronização foi consolidada em `app.utils.deps`)


def get_login_url(state: str | None = None):
    """Gera a URL de login do Auth0 (com Google).

    Se `state` for fornecido, será adicionado ao parâmetro `state` da URL
    do Auth0 para que o callback possa redirecionar de volta ao front.
    (Nota: o parâmetro `raw` foi removido — retornos JSON expostos não são seguros.)
    """
    # Seleciona callback de acordo com o ambiente
    callback_url = os.getenv("AUTH0_CALLBACK_URL")
    if not callback_url:
        if os.getenv("ENVIRONMENT") == "production":
            callback_url = "https://api.hominsaude.cloud/auth/callback"
        else:
            callback_url = "http://localhost:8000/auth/callback"

    # NOTE: previously supported a `raw` flag to return tokens as JSON in dev.
    # That behavior was removed for security and simplicity.

    url = (
        f"https://{AUTH0_DOMAIN}/authorize"
        f"?response_type=code"
        f"&client_id={AUTH0_CLIENT_ID}"
        f"&redirect_uri={callback_url}"
        f"&scope=openid profile email"
        f"&audience={AUTH0_AUDIENCE}"
        f"&connection=google-oauth2"
    )

    if state:
        # state deve estar URL-encoded pelo caller
        url = f"{url}&state={state}"

    return url


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


# DEPENDÊNCIAS PARA PROTEÇÃO DE ROTAS

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


# ============================================
# FUNÇÕES PARA REGISTRO E LOGIN COM EMAIL/SENHA
# ============================================

def register_user_auth0(email: str, password: str, name: str) -> dict:
    """
    Registra um novo usuário no Auth0 usando email e senha.
    
    Args:
        email: Email do usuário
        password: Senha do usuário
        name: Nome completo do usuário
    
    Returns:
        dict: Dados do usuário criado no Auth0
    
    Raises:
        HTTPException: Se houver erro no registro
    """
    # URL da Management API do Auth0 para criar usuários
    # Primeiro, precisamos obter um Management API token
    
    try:
        # 1. Obter Management API Token (Client Credentials flow)
        token_url = f"https://{AUTH0_DOMAIN}/oauth/token"
        token_payload = {
            "grant_type": "client_credentials",
            "client_id": AUTH0_CLIENT_ID,
            "client_secret": AUTH0_CLIENT_SECRET,
            "audience": f"https://{AUTH0_DOMAIN}/api/v2/"
        }
        
        token_response = requests.post(token_url, json=token_payload)
        if token_response.status_code != 200:
            raise HTTPException(
                status_code=500,
                detail=f"Erro ao obter token de gerenciamento: {token_response.text}"
            )
        
        mgmt_token = token_response.json()["access_token"]
        
        # 2. Criar usuário via Management API
        create_user_url = f"https://{AUTH0_DOMAIN}/api/v2/users"
        headers = {
            "Authorization": f"Bearer {mgmt_token}",
            "Content-Type": "application/json"
        }
        
        user_payload = {
            "email": email,
            "password": password,
            "name": name,
            "connection": "Username-Password-Authentication",  # Database connection padrão do Auth0
            "email_verified": False,  # Requer verificação de email
            "app_metadata": {},
            "user_metadata": {
                "auth_provider": "email"
            }
        }
        
        create_response = requests.post(create_user_url, json=user_payload, headers=headers)
        
        if create_response.status_code == 409:
            # Usuário já existe
            raise HTTPException(
                status_code=400,
                detail="Email já cadastrado no sistema"
            )
        elif create_response.status_code != 201:
            error_detail = create_response.json().get("message", create_response.text)
            raise HTTPException(
                status_code=400,
                detail=f"Erro ao criar usuário: {error_detail}"
            )
        
        user_data = create_response.json()
        return user_data
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno ao registrar usuário: {str(e)}"
        )


def login_with_password(email: str, password: str) -> dict:
    """
    Realiza login com email e senha usando Resource Owner Password Grant.
    
    Args:
        email: Email do usuário
        password: Senha do usuário
    
    Returns:
        dict: Tokens de acesso (access_token, id_token, expires_in)
    
    Raises:
        HTTPException: Se credenciais forem inválidas
    """
    try:
        # Usar /oauth/token com grant_type http://auth0.com/oauth/grant-type/password-realm
        token_url = f"https://{AUTH0_DOMAIN}/oauth/token"
        
        payload = {
            "grant_type": "http://auth0.com/oauth/grant-type/password-realm",
            "username": email,
            "password": password,
            "client_id": AUTH0_CLIENT_ID,
            "client_secret": AUTH0_CLIENT_SECRET,
            "audience": AUTH0_AUDIENCE,
            "scope": "openid profile email",
            "realm": "Username-Password-Authentication"  # Database connection name
        }
        
        response = requests.post(token_url, json=payload)
        
        if response.status_code == 403:
            raise HTTPException(
                status_code=401,
                detail="Credenciais inválidas. Verifique email e senha."
            )
        elif response.status_code != 200:
            error_data = response.json()
            error_msg = error_data.get("error_description", "Erro ao fazer login")
            error_code = error_data.get("error", "unknown_error")
            
            # Log detalhado para debug
            print(f"❌ Auth0 Login Error: {error_code} - {error_msg}")
            print(f"📄 Full response: {error_data}")
            
            raise HTTPException(
                status_code=401,
                detail=f"{error_msg} (error: {error_code})"
            )
        
        token_data = response.json()
        return token_data
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno ao fazer login: {str(e)}"
        )
