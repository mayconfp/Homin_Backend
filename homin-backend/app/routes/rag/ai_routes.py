from fastapi import APIRouter
from app.services.ai_service import gerar_resposta
from .schema import ChatIn, ChatOut

router = APIRouter(prefix="/ai", tags=["AI"])

@router.post("/chat", response_model=ChatOut)
async def chat_with_ai(request: ChatIn) -> ChatOut:
    """
    Endpoint para chat.
    
    Envia uma mensagem e recebe resp da ia.
    """
    try:
        resposta = gerar_resposta([], request.message)
        return ChatOut(response=resposta)
    except Exception as e:
        return ChatOut(response=f"Erro ao processar mensagem: {str(e)}")


# @router.post("/analyze-document")
# async def analyze_document(document_id: int):
#     """Endpoint para análise de documento com IA"""
#     pass

# @router.post("/generate-summary")
# async def generate_summary(text: str):
#     """Endpoint para gerar resumo usando IA"""
#     pass