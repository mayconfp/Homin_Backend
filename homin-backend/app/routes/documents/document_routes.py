import os
import uuid
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, status
from sqlalchemy import select
from app.core.permissions import Permissions
from app.database.models import Documento
from app.utils.deps import SessionDep, LocalUserDep, LoggedUserDep
from app.utils.permission_utils import validate_permission
from app.services.document_service import criar_db_async
from app.routes.documents.schema import DocumentOut, DocumentCreate, DocumentList, DocumentsListResponse, MessageResponse, DocumentList

router = APIRouter(prefix="/documents", tags=["Documents"])

# diretório de base para documentos (usa caminho absoluto para evitar inconsistências de cwd)
BASE_DOCS_DIR = Path(__file__).resolve().parents[2] / "base_conhecimento"



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
        # caminho absoluto consistente com o indexador
        BASE_DOCS_DIR.mkdir(parents=True, exist_ok=True)
        file_path = BASE_DOCS_DIR / safe_filename

        # salvar no banco de dados
        novo_documento = Documento(
            id_usuario=user.id_usuario,
            nome_arquivo=safe_filename,
            tipo_documento=file.content_type or "application/pdf"
        )
        db_session.add(novo_documento)
        await db_session.commit()
        await db_session.refresh(novo_documento)

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
        base_path = str(BASE_DOCS_DIR)
        BASE_DOCS_DIR.mkdir(parents=True, exist_ok=True)

        # 1) Buscar documentos no banco
        stmt = select(Documento)
        documentos_no_banco = await db_session.scalars(stmt)
        documentos_no_banco = list(documentos_no_banco)
        nomes_no_banco = {d.nome_arquivo for d in documentos_no_banco if d.nome_arquivo}

        lista_documentos: list[DocumentList] = []

        # adicionar registros que estão no banco (mesmo se arquivo físico estiver ausente)
        for doc in documentos_no_banco:
            caminho_arquivo = os.path.join(base_path, doc.nome_arquivo or "")
            existe = os.path.exists(caminho_arquivo)
            tamanho = os.path.getsize(caminho_arquivo) if existe else 0
            lista_documentos.append(DocumentList(
                id_documento=doc.id_documento,
                filename=doc.nome_arquivo,
                size_bytes=tamanho,
                in_db=True,
                on_disk=existe
            ))

        # 2) Buscar arquivos no disco que não estão no banco e incluí-los
        for nome_arquivo in os.listdir(base_path):
            if not nome_arquivo.lower().endswith('.pdf'):
                continue
            if nome_arquivo in nomes_no_banco:
                continue
            caminho_arquivo = os.path.join(base_path, nome_arquivo)
            tamanho = os.path.getsize(caminho_arquivo)
            lista_documentos.append(DocumentList(
                id_documento=None,  # Sem ID pois não está no banco
                filename=nome_arquivo,
                size_bytes=tamanho,
                in_db=False,
                on_disk=True
            ))                                                      

        return DocumentsListResponse(documents=lista_documentos)
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
        file_path = BASE_DOCS_DIR / documento.nome_arquivo
        if file_path.exists():
            file_path.unlink()

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
        # Reindexa toda a base de conhecimento.
        # Opcionalmente suportamos reindex via filename no corpo/query no futuro.
        await criar_db_async()
        return {"message": "Base de conhecimento reprocessada com sucesso"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao reprocessar base: {str(e)}")


@router.post("/sync-to-db")
async def sync_disk_to_db(user: LoggedUserDep, db_session: SessionDep):
    """Cria registros `Documento` no Postgres para arquivos que existem em
    `app/base_conhecimento` mas não estão registrados no banco.
    Retorna a lista de arquivos adicionados.
    """
    await validate_permission(user, Permissions.ADMIN_DOCUMENTS)

    try:
        base_path = str(BASE_DOCS_DIR)
        BASE_DOCS_DIR.mkdir(parents=True, exist_ok=True)

        # arquivos no disco
        disk_files = [f for f in os.listdir(base_path) if f.lower().endswith('.pdf')]

        # arquivos no DB
        stmt = select(Documento)
        docs_in_db = await db_session.scalars(stmt)
        db_filenames = {d.nome_arquivo for d in docs_in_db if d.nome_arquivo}

        to_add = [f for f in disk_files if f not in db_filenames]
        added = []

        for filename in to_add:
            novo_documento = Documento(
                id_usuario=user.id_usuario,
                nome_arquivo=filename,
                tipo_documento='application/pdf'
            )
            db_session.add(novo_documento)
            added.append(filename)

        if added:
            await db_session.commit()

        return {"added": added, "count": len(added)}
    except Exception as e:
        await db_session.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao sincronizar disco->DB: {str(e)}")
