from pydantic import BaseModel, Field

class ChatIn(BaseModel):
    message: str = Field(min_length=1, description="Mensagem para a IA")

class ChatOut(BaseModel):
    response: str = Field(description="Resposta da IA")