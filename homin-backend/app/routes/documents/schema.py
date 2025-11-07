from pydantic import BaseModel, Field
from datetime import datetime
import uuid
from typing import Optional, List

class DocumentOut(BaseModel):
    id_documento: uuid.UUID
    id_usuario: uuid.UUID
    nome_arquivo: str
    tipo_documento: Optional[str]
    data_criacao: datetime
    
    class Config:
        from_attributes = True

class DocumentCreate(BaseModel):
    # Para uploads via UploadFile, não precisa de campos
    pass

class DocumentList(BaseModel):
    filename: str
    size_bytes: int

class DocumentsListResponse(BaseModel):
    documents: List[DocumentList]

class MessageResponse(BaseModel):
    message: str

class MessageResponse(BaseModel):
    message: str