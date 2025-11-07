from typing import Dict, List
from fastapi import HTTPException, status
from app.core.permissions import Permissions


class PermissionError(HTTPException):
    """Erro customizado para permissões"""
    def __init__(self, permission: str):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Você não tem permissão para realizar a ação ({permission})"
        )


async def user_has_permission(user_data: Dict, permission: Permissions) -> bool:
    """
    Verifica se o usuário tem uma permissão específica baseado no token JWT do Auth0
    
    Args:
        user_data: Payload do JWT decodificado
        permission: Permissão a ser verificada
    
    Returns:
        bool: True se o usuário tem a permissão
    """
    # Buscar permissões no token JWT
    user_permissions = user_data.get("permissions", [])
    
    # Fallback: buscar em scope se não tiver permissions
    if not user_permissions:
        scope = user_data.get("scope", "")
        user_permissions = scope.split() if scope else []
    
    # FALLBACK: Todo usuário logado automaticamente tem chat:access
    if permission == Permissions.CHAT_ACCESS:
        return True
    
    # Verificar permissão exata
    if permission.value in user_permissions:
        return True
    
    # Verificar permissões hierárquicas (ex: admin:documents cobre admin:documents.read)
    for user_perm in user_permissions:
        if permission.value.startswith(user_perm + "."):
            return True
    
    return False


async def validate_permission(user_data: Dict, permission: Permissions):
    """
    Valida se o usuário tem a permissão necessária, levanta exceção se não tiver
    
    Args:
        user_data: Payload do JWT decodificado
        permission: Permissão a ser verificada
    
    Raises:
        PermissionError: Se o usuário não tem a permissão
    """
    if not await user_has_permission(user_data, permission):
        raise PermissionError(permission.value)


def require_permissions(*permissions: Permissions):
    """
     para criar dependency que valida múltiplas permissões
    
    Args:
        *permissions: Permissões necessárias (qualquer uma serve)
    
    Returns:
        Função de dependência
    """
    async def check_permissions(user_data: Dict):
        has_any = False
        for permission in permissions:
            if await user_has_permission(user_data, permission):
                has_any = True
                break
        
        if not has_any:
            perm_names = [p.value for p in permissions]
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Uma das seguintes permissões é necessária: {', '.join(perm_names)}"
            )
        return user_data
    
    return check_permissions


def require_all_permissions(*permissions: Permissions):
    """
    Factory para criar dependency que valida TODAS as permissões
    
    Args:
        *permissions: Todas as permissões necessárias
    
    Returns:
        Função de dependência
    """
    async def check_all_permissions(user_data: Dict):
        for permission in permissions:
            if not await user_has_permission(user_data, permission):
                raise PermissionError(permission.value)
        return user_data
    
    return check_all_permissions