"""
Schemas Pydantic para rotas de conta (registro e login com email/senha)
"""
from datetime import datetime
from typing import Optional
import re

from pydantic import BaseModel, EmailStr, Field, field_validator


class RegisterIn(BaseModel):
    """Schema para registro de novo usuário com email/senha"""
    email: EmailStr = Field(..., description="Email do usuário")
    password: str = Field(..., min_length=8, description="Senha (mínimo 8 caracteres)")
    name: str = Field(..., min_length=2, max_length=255, description="Nome completo do usuário")
    
    @field_validator('password')
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Validar força da senha"""
        if not any(char.isdigit() for char in v):
            raise ValueError('Senha deve conter pelo menos um número')
        if not any(char.isupper() for char in v):
            raise ValueError('Senha deve conter pelo menos uma letra maiúscula')
        if not any(char.islower() for char in v):
            raise ValueError('Senha deve conter pelo menos uma letra minúscula')
        # Validar caractere especial
        if not re.search(r'[!@#$%^&*(),.?":{}|<>_\-+=\[\]\\\/;`~]', v):
            raise ValueError('Senha deve conter pelo menos um caractere especial (!@#$%^&*...)')
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "email": "usuario@exemplo.com",
                "password": "SenhaForte@123",
                "name": "João Silva"
            }
        }


class LoginPasswordIn(BaseModel):
    """Schema para login com email e senha"""
    email: EmailStr = Field(..., description="Email do usuário")
    password: str = Field(..., description="Senha do usuário")
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "usuario@exemplo.com",
                "password": "SenhaForte123"
            }
        }


class LoginOut(BaseModel):
    """Schema para resposta de login bem-sucedido"""
    access_token: str = Field(..., description="Token JWT de acesso")
    token_type: str = Field(default="Bearer", description="Tipo do token")
    expires_in: int = Field(..., description="Tempo de expiração em segundos")
    user: "UserOut" = Field(..., description="Dados do usuário autenticado")
    
    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "Bearer",
                "expires_in": 86400,
                "user": {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "email": "usuario@exemplo.com",
                    "name": "João Silva",
                    "role": "user",
                    "auth_provider": "email"
                }
            }
        }


class UserOut(BaseModel):
    """Schema para dados do usuário (resposta)"""
    id: str = Field(..., description="ID do usuário (UUID)")
    email: str = Field(..., description="Email do usuário")
    name: str = Field(..., description="Nome do usuário")
    role: str = Field(..., description="Role do usuário (user/admin)")
    auth_provider: Optional[str] = Field(None, description="Provedor de autenticação (google/email/facebook)")
    created_at: Optional[datetime] = Field(None, description="Data de cadastro")
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "email": "usuario@exemplo.com",
                "name": "João Silva",
                "role": "user",
                "auth_provider": "email",
                "created_at": "2025-11-25T10:30:00Z"
            }
        }


class RegisterOut(BaseModel):
    """Schema para resposta de registro bem-sucedido"""
    message: str = Field(..., description="Mensagem de sucesso")
    user: UserOut = Field(..., description="Dados do usuário criado")
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Usuário criado com sucesso! Verifique seu email para confirmar a conta.",
                "user": {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "email": "usuario@exemplo.com",
                    "name": "João Silva",
                    "role": "user",
                    "auth_provider": "email",
                    "created_at": "2025-11-25T10:30:00Z"
                }
            }
        }


class ErrorResponse(BaseModel):
    """Schema para respostas de erro"""
    error: str = Field(..., description="Tipo do erro")
    detail: str = Field(..., description="Detalhes do erro")
    
    class Config:
        json_schema_extra = {
            "example": {
                "error": "validation_error",
                "detail": "Email já cadastrado no sistema"
            }
        }
