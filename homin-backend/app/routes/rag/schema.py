from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class ChatIn(BaseModel):
    message: str = Field(min_length=1, description="Mensagem para a IA")
    conversa_id: Optional[int] = Field(None, description="ID da conversa existente (opcional para nova conversa)")

class ChatOut(BaseModel):
    response: str = Field(description="Resposta da IA")
    conversa_id: int = Field(description="ID da conversa")
    origem_contexto: str = Field(description="Origem do contexto usado (local/web/social)")

class ConversaCreate(BaseModel):
    titulo: Optional[str] = Field(None, description="Título da conversa")

class ConversaOut(BaseModel):
    id_conversa: int
    titulo: Optional[str]
    data_inicio: datetime
    data_ultima_msg: Optional[datetime]
    
    class Config:
        from_attributes = True

class MensagemHistorico(BaseModel):
    id_historico: int
    mensagem_texto: str
    tipo: str  # 'user' ou 'assistant'
    origem_contexto: str
    data_hora: datetime
    
    class Config:
        from_attributes = True

class ConversaComHistorico(BaseModel):
    conversa: ConversaOut
    historico: List[MensagemHistorico]

class ConversasListResponse(BaseModel):
    conversas: List[ConversaOut]