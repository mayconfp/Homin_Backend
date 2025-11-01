from enum import Enum


class Permissions(str, Enum):
   # Permissões de acesso
    
    # Usuarios comuns apenas chat

    CHAT_ACCESS = "chat:access"
    
   
    # área admin completa pd fazer tudo

    ADMIN_DOCUMENTS = "admin:documents"  # Upload, listar, deletar documentos
    ADMIN_USERS = "admin:users"          # Listar usuários não implementado ainda p ver usuários