import os
import uuid
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, status
from sqlalchemy import select
from app.core.permissions import Permissions
from app.database.models import Documento
from app.utils.deps import SessionDep, LocalUserDep
from app.services.auth import LoggedUserDep
from app.utils.permission_utils import validate_permission
from app.services.document_service import criar_db_async
from app.routes.documents.schema import DocumentOut, DocumentCreate, DocumentList, DocumentsListResponse, MessageResponse, DocumentList

router = APIRouter(prefix="/documents", tags=["Documents"])


# apenas admin pode subir documentos que manda para o postgre e salva na base para IA 
@router.post("/upload", status_code=status.HTTP_201_CREATED, response_model=DocumentOut)
async def upload_document(
    user: LocalUserDep,
    auth_user: LoggedUserDep,
    db_session: SessionDep,
    file: UploadFile = File(...),
):
    # Admin pode fazer tudo com documentos
    await validate_permission(auth_user, Permissions.ADMIN_DOCUMENTS)
    
    try:
        safe_filename = Path(file.filename).name
        file_path = f"app/base_conhecimento/{safe_filename}"
        
        # salvar no banco de dados
        novo_documento = Documento(
            id_usuario=user.id_usuario,
            nome_arquivo=safe_filename,
            tipo_documento=file.content_type or "application/pdf"
        )
        db_session.add(novo_documento)
        await db_session.commit()
        await db_session.refresh(novo_documento)

        os.makedirs("app/base_conhecimento", exist_ok=True)
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        await criar_db_async()

        return novo_documento
    except Exception as e:
        await db_session.rollback()  #  tudo funciona ou nada funciona
        raise HTTPException(status_code=500, detail=f"Erro ao processar documento: {str(e)}")


#lista documento da base e só apenas adm pode ver
@router.get("/list", response_model=DocumentsListResponse)
async def listar_documentos(
    user: LocalUserDep,
    auth_user: LoggedUserDep,
    db_session: SessionDep,
):
    await validate_permission(auth_user, Permissions.ADMIN_DOCUMENTS)

    try:
        base_path = "app/base_conhecimento"
        if not os.path.exists(base_path):
            return DocumentsListResponse(documents=[])
        
        documents = []
        for filename in os.listdir(base_path):
            if filename.endswith('.pdf'):
                file_path = os.path.join(base_path, filename)
                size = os.path.getsize(file_path)
                documents.append(DocumentList(
                    filename=filename,
                    size_bytes=size
                ))
        
        return DocumentsListResponse(documents=documents)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao listar documentos: {str(e)}")


#deletar pelo id unico e apagar da base de conhecimento apenas adm apaga documentos
@router.delete("/{documento_id}")
async def delete_documento(
    documento_id: uuid.UUID,
    user: LoggedUserDep,
    db_session: SessionDep
):
    await validate_permission(user, Permissions.ADMIN_DOCUMENTS)

    try:
        # Buscar documento no banco
        stmt = select(Documento).where(Documento.id_documento == documento_id)
        documento = await db_session.scalar(stmt)
        
        if not documento:
            raise HTTPException(status_code=404, detail="Documento não encontrado")

        # Remover arquivo físico
        file_path = f"app/base_conhecimento/{documento.nome_arquivo}"
        if os.path.exists(file_path):
            os.remove(file_path)

        # Remover do banco
        await db_session.delete(documento)
        await db_session.commit()

        return {"message": f"Documento {documento.nome_arquivo} removido com sucesso"}
    except Exception as e:
        await db_session.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao remover documento: {str(e)}")


# serve para reindexar documentos caso upload falhe no meio do processo
@router.post("/reindex")
async def reindexar_documents(user: LoggedUserDep, db_session: SessionDep):
    await validate_permission(user, Permissions.ADMIN_DOCUMENTS)
    
    try:
        await criar_db_async()  # Só reprocessa, não modifica DB
        return {"message": "Base de conhecimento reprocessada com sucesso"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao reprocessar base: {str(e)}")
