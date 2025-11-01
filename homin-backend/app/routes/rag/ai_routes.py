from fastapi import APIRouter, Depends
from app.services.ai_service import gerar_resposta
from app.services.auth import LoggedUserDep, require_permission_new
from app.core.permissions import Permissions
from app.utils.permission_utils import validate_permission
from .schema import ChatIn, ChatOut

router = APIRouter(prefix="/ai", tags=["AI"])

@router.post("/chat", response_model=ChatOut)
async def chat_with_ai(
    request: ChatIn,
    user: LoggedUserDep
) -> ChatOut:
    """
    Endpoint para chat com IA - requer login e permissão chat:access.
    
    Envia uma mensagem e recebe resp da ia.
    """
    # Validar permissão usando o novo sistema
    await validate_permission(user, Permissions.CHAT_ACCESS)
    
    try:
        resposta = await gerar_resposta([], request.message)
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