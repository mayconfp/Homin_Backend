# Rotas para gerenciamento de documentos (ADMIN)
# Endpoints para CRUD de documentos - apenas administradores

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from typing import List
from app.services.auth import LoggedUserDep
from app.core.permissions import Permissions
from app.utils.permission_utils import validate_permission
from app.services.document_service import criar_db_async
import os

router = APIRouter(prefix="/documents", tags=["Documents"])

@router.post("/upload")
async def upload_document(
    user: LoggedUserDep,
    file: UploadFile = File(...)
):
    """Endpoint para upload de documento - apenas admin"""
    # Admin pode fazer tudo com documentos
    await validate_permission(user, Permissions.ADMIN_DOCUMENTS)
    
    try:
        # Salvar arquivo na pasta base_conhecimento
        file_path = f"app/base_conhecimento/{file.filename}"
        
        # Criar diretório se não existir
        os.makedirs("app/base_conhecimento", exist_ok=True)
        
        # Salvar arquivo
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Reprocessar base de conhecimento
        await criar_db_async()
        
        return {"message": f"Documento {file.filename} enviado e processado com sucesso"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao processar documento: {str(e)}")


@router.get("/list")
async def list_documents(user: LoggedUserDep):
    """Listar documentos na base de conhecimento - apenas admin"""
    # Admin pode fazer tudo com documentos
    await validate_permission(user, Permissions.ADMIN_DOCUMENTS)
    
    try:
        base_path = "app/base_conhecimento"
        if not os.path.exists(base_path):
            return {"documents": []}
        
        documents = []
        for filename in os.listdir(base_path):
            if filename.endswith('.pdf'):
                file_path = os.path.join(base_path, filename)
                size = os.path.getsize(file_path)
                documents.append({
                    "filename": filename,
                    "size_bytes": size
                })
        
        return {"documents": documents}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao listar documentos: {str(e)}")


@router.delete("/{filename}")
async def delete_document(filename: str, user: LoggedUserDep):
    """Deletar documento - apenas admin"""
    # Admin pode fazer tudo com documentos
    await validate_permission(user, Permissions.ADMIN_DOCUMENTS)
    
    try:
        file_path = f"app/base_conhecimento/{filename}"
        
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Documento não encontrado")
        
        os.remove(file_path)
        
        # Reprocessar base de conhecimento
        await criar_db_async()
        
        return {"message": f"Documento {filename} removido com sucesso"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao remover documento: {str(e)}")


@router.post("/reindex")
async def reindex_documents(user: LoggedUserDep):
    """Reprocessar toda a base de conhecimento - apenas admin"""
    # Admin pode fazer tudo com documentos
    await validate_permission(user, Permissions.ADMIN_DOCUMENTS)
    
    try:
        await criar_db_async()
        return {"message": "Base de conhecimento reprocessada com sucesso"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao reprocessar base: {str(e)}")
    
    
#     """Endpoint para obter documento específico"""
#     pass

# @router.put("/{document_id}")
# async def update_document(document_id: int, document: DocumentUpdate):
#     """Endpoint para atualizar documento"""
#     pass

# @router.delete("/{document_id}")
# async def delete_document(document_id: int):
#     """Endpoint para deletar documento"""
#     pass

# @router.post("/{document_id}/upload")
# async def upload_file_to_document(document_id: int, file: UploadFile):
#     """Endpoint para upload de arquivo para documento"""
#     pass