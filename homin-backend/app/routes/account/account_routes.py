"""
Rotas de gerenciamento de conta - Registro e Login com Email/Senha
"""
import os

from fastapi import APIRouter, HTTPException, status, Response
from sqlalchemy import select

from app.database.models import Usuario
from app.services.auth import register_user_auth0, login_with_password
from app.utils.deps import SessionDep, sync_user_to_local_db, verify_jwt
from app.utils.security import hash_password
from .schema import (
    RegisterIn, 
    RegisterOut, 
    LoginPasswordIn, 
    LoginOut, 
    UserOut,
    ErrorResponse
)

router = APIRouter(prefix="/account", tags=["Account Management"])


@router.post(
    "/register",
    response_model=RegisterOut,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Email já cadastrado ou dados inválidos"},
        500: {"model": ErrorResponse, "description": "Erro interno do servidor"}
    }
)
async def register_user(
    user_data: RegisterIn,
    db_session: SessionDep
):
    """
    Registra um novo usuário no sistema usando email e senha.
    
    - Cria usuário no Auth0 (Database connection) - Auth0 gerencia a senha
    - Sincroniza metadados com PostgreSQL local
    - Envia email de verificação automaticamente (configurado no Auth0)
    
    **Requisitos de senha:**
    - Mínimo 8 caracteres
    - Pelo menos uma letra maiúscula
    - Pelo menos uma letra minúscula
    - Pelo menos um número
    - Pelo menos um caractere especial (!@#$%^&*...)
    """
    try:
        # 1. Verificar se email já existe na base local
        stmt = select(Usuario).where(Usuario.email == user_data.email)
        existing_user = await db_session.scalar(stmt)
        
        if existing_user:
            raise HTTPException(
                status_code=400,
                detail="Email já cadastrado no sistema"
            )
        
        # 2. Hash da senha para armazenar localmente
        password_hashed = hash_password(user_data.password)
        
        # 3. Criar usuário no Auth0 (Auth0 gerencia hash da senha internamente)
        auth0_user = register_user_auth0(
            email=user_data.email,
            password=user_data.password,
            name=user_data.name
        )
        
        # 4. Criar usuário na base local com hash da senha
        new_user = Usuario(
            email=user_data.email,
            nome=user_data.name,
            password_hash=password_hashed,  # Armazenar hash localmente
            auth0_sub=auth0_user.get("user_id"),
            role="user",
            auth_provider="email"
        )
        
        db_session.add(new_user)
        await db_session.commit()
        await db_session.refresh(new_user)
        
        # 5. Preparar resposta
        user_out = UserOut(
            id=str(new_user.id_usuario),
            email=new_user.email,
            name=new_user.nome,
            role=new_user.role,
            auth_provider=new_user.auth_provider,
            created_at=new_user.data_cadastro
        )
        
        return RegisterOut(
            message="Usuário criado com sucesso! Verifique seu email para confirmar a conta.",
            user=user_out
        )
        
    except HTTPException:
        raise
    except Exception as e:
        # Rollback em caso de erro
        await db_session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao registrar usuário: {str(e)}"
        )


@router.post(
    "/login",
    response_model=LoginOut,
    responses={
        401: {"model": ErrorResponse, "description": "Credenciais inválidas"},
        500: {"model": ErrorResponse, "description": "Erro interno do servidor"}
    }
)
async def login_with_email_password(
    credentials: LoginPasswordIn,
    response: Response,
    db_session: SessionDep
):
    """
    Realiza login com email e senha.
    
    - Autentica no Auth0 usando Resource Owner Password Grant
    - Retorna access_token JWT
    - Define cookie HttpOnly com o token (segurança)
    - Sincroniza dados do usuário com PostgreSQL local
    
    **Nota:** Usuário deve ter verificado o email para fazer login (configurável no Auth0).
    """
    try:
        # 1. Autenticar no Auth0
        token_data = login_with_password(
            email=credentials.email,
            password=credentials.password
        )
        
        access_token = token_data["access_token"]
        expires_in = token_data.get("expires_in", 86400)
        
        # 2. Decodificar JWT para extrair dados do usuário (SEM chamar /userinfo!)
        payload = verify_jwt(access_token)
        
        # 3. Sincronizar com base local usando dados do JWT
        local_user = await sync_user_to_local_db(access_token, payload, db_session)
        
        # 4. Atualizar auth_provider se necessário
        if not local_user.auth_provider or local_user.auth_provider != "email":
            local_user.auth_provider = "email"
            await db_session.commit()
        
        # 5. Configurar cookie HttpOnly
        secure_flag = os.getenv("ENVIRONMENT") == "production"
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=secure_flag,
            samesite="lax",
            max_age=expires_in
        )
        
        # 6. Preparar resposta
        user_out = UserOut(
            id=str(local_user.id_usuario),
            email=local_user.email,
            name=local_user.nome,
            role=local_user.role,
            auth_provider=local_user.auth_provider,
            created_at=local_user.data_cadastro
        )
        
        return LoginOut(
            access_token=access_token,
            token_type="Bearer",
            expires_in=expires_in,
            user=user_out
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao fazer login: {str(e)}"
        )


@router.post("/verify-email/{token}")
async def verify_email_token(token: str):
    """
    Endpoint para verificação de email (placeholder).
    
    A verificação é gerenciada automaticamente pelo Auth0.
    Este endpoint pode ser usado para callbacks customizados se necessário.
    """
    return {
        "message": "Verificação de email é gerenciada pelo Auth0",
        "status": "redirect_to_auth0"
    }


@router.post("/request-password-reset")
async def request_password_reset(email: str):
    """
    Solicita reset de senha (placeholder).
    
    Para implementar:
    1. Chamar Auth0 Management API para enviar email de reset
    2. Ou redirecionar para página de reset do Auth0
    """
    return {
        "message": "Email de recuperação de senha enviado (se o email existir)",
        "status": "check_email"
    }
