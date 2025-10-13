from pydantic import BaseModel, Field

class DocumentIn(BaseModel):
    title: str = Field(min_length=1, description="Título do documento")
    content: str = Field(min_length=1, description="Conteúdo do documento")

class DocumentOut(BaseModel):
    id: int = Field(description="ID do documento")
    title: str = Field(description="Título do documento")
    content: str = Field(description="Conteúdo do documento")