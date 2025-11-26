import os
import json
import requests
from typing import Annotated, AsyncGenerator, Dict
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import selectinload
from jose import jwt
from dotenv import load_dotenv

from app.database.models import Usuario
from app.database.config import get_async_db

load_dotenv()

AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
AUTH0_CLIENT_ID = os.getenv("AUTH0_CLIENT_ID")
AUTH0_AUDIENCE = os.getenv("AUTH0_AUDIENCE", f"https://{AUTH0_DOMAIN}/api/v2/")

security = HTTPBearer(auto_error=False)

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
                issuer=f"https://{AUTH0_DOMAIN}/",
            )
            return payload
        else:
            raise HTTPException(status_code=401, detail="Não foi possível verificar o token")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.JWTClaimsError:
        raise HTTPException(status_code=401, detail="Claims inválidos")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Token inválido: {str(e)}")

async def get_session():
    """Dependência para obter sessão do banco de dados"""
    async for session in get_async_db():
        yield session

async def sync_user_to_local_db(token: str, payload: Dict, db_session: AsyncSession) -> Usuario:
    """Sincroniza usuário do Auth0 para a base local e retorna o objeto Usuario"""
    try:
        # Tentar obter email do payload primeiro
        email = payload.get("email")
        nome = payload.get("name")
        
        # Se não tiver email no payload, buscar no /userinfo
        if not email:
            print(f"⚠️ Email não encontrado no payload JWT. Buscando no /userinfo...")
            try:
                userinfo_url = f"https://{AUTH0_DOMAIN}/userinfo"
                headers = {"Authorization": f"Bearer {token}"}
                response = requests.get(userinfo_url, headers=headers, timeout=5)
                
                if response.status_code == 200:
                    userinfo = response.json()
                    email = userinfo.get("email")
                    if not nome:
                        nome = userinfo.get("name", userinfo.get("nickname", None))
                    print(f"✅ Email obtido do /userinfo: {email}")
                else:
                    print(f"⚠️ Erro ao buscar /userinfo. Status: {response.status_code}")
            except requests.exceptions.RequestException as req_error:
                print(f"⚠️ Erro ao conectar com /userinfo: {req_error}")
        
        # Se ainda assim não tiver email, lançar erro
        if not email:
            raise ValueError("Email não encontrado no token ou userinfo do Auth0")
        
        # Buscar usuário na base local
        stmt = select(Usuario).where(Usuario.email == email)
        user = await db_session.scalar(stmt)
        
        if not user:
            # Criar novo usuário
            user = Usuario(
                email=email,
                nome=nome or email.split("@")[0],
                role="user"
            )
            db_session.add(user)
            await db_session.commit()
            await db_session.refresh(user)
            print(f"✅ Novo usuário criado na base local: {email}")
        else:
            # Atualizar nome se necessário
            if nome and user.nome != nome:
                user.nome = nome
                await db_session.commit()
                print(f"✅ Usuário atualizado: {email}")
                
        return user
    except ValueError as ve:
        # Erro de validação (email faltando)
        print(f"❌ Erro ao sincronizar usuário: {ve}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        print(f"❌ Erro inesperado ao sincronizar usuário: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao sincronizar usuário: {str(e)}")

async def get_logged_user(
    db_session: "SessionDep",
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Dict:
    """Obter usuário logado validando Auth0 JWT + sincronizar na base local"""
    try:
        token = None
        if credentials and getattr(credentials, "credentials", None):
            token = credentials.credentials
        else:
            # fallback para cookie (usado por frontend no callback)
            token = request.cookies.get("access_token")

        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token não fornecido",
                headers={"WWW-Authenticate": "Bearer"},
            )

        payload = verify_jwt(token)

        # Sincronizar com base local (não bloqueia se der erro)
        await sync_user_to_local_db(token, payload, db_session)

        return payload
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token inválido: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_local_user(
    db_session: "SessionDep",
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Usuario:
    """Obter objeto `Usuario` da base local após validação Auth0.

    Aceita token via header `Authorization: Bearer <token>` preferencialmente,
    com fallback para cookie `access_token` (para compatibilidade com callback).
    """
    try:
        token = None
        if credentials and getattr(credentials, "credentials", None):
            token = credentials.credentials
        else:
            token = request.cookies.get("access_token")

        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token não fornecido",
                headers={"WWW-Authenticate": "Bearer"},
            )

        payload = verify_jwt(token)

        # Sincronizar com base local e retornar objeto Usuario
        user = await sync_user_to_local_db(token, payload, db_session)

        return user
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token inválido: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

# Type annotations para dependências
SessionDep = Annotated[AsyncSession, Depends(get_session)]
LoggedUserDep = Annotated[Dict, Depends(get_logged_user)]
LocalUserDep = Annotated[Usuario, Depends(get_local_user)]


# Permissões: helper para usar em routes (compatível com validate_permission)
from app.core.permissions import Permissions
from app.utils.permission_utils import validate_permission


def require_permission(permission: Permissions):
    """Factory que retorna uma dependency que valida a permissão e retorna o user payload"""
    async def check_permission(user_data: Dict = Depends(LoggedUserDep)):
        await validate_permission(user_data, permission)
        return user_data

    return check_permission