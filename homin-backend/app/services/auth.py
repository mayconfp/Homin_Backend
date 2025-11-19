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
