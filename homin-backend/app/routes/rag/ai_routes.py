from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, desc
from app.services.ai_service import gerar_resposta
from app.services.auth import LoggedUserDep, require_permission_new
from app.core.permissions import Permissions
from app.utils.permission_utils import validate_permission
from app.utils.deps import SessionDep, LocalUserDep
from app.database.models import Conversa, HistoricoMensagem
from .schema import (
    ChatIn, ChatOut, ConversaCreate, ConversaOut, 
    ConversaComHistorico, ConversasListResponse, MensagemHistorico
)

router = APIRouter(prefix="/ai", tags=["AI"])

@router.post("/chat", response_model=ChatOut)
async def chat_with_ai(
    request: ChatIn,
    user: LocalUserDep,
    auth_user: LoggedUserDep,
    db_session: SessionDep
) -> ChatOut:
    """
    Endpoint para chat com IA - requer login e permissão chat:access.
    
    Envia uma mensagem e recebe resposta da IA.
    Salva a conversa e o histórico no banco.
    """
    # Validar permissão usando o novo sistema
    await validate_permission(auth_user, Permissions.CHAT_ACCESS)
    
    try:
        # 1. Buscar ou criar conversa
        conversa = None
        historico_conversa = ""
        
        if request.conversa_id:
            # Buscar conversa existente
            stmt = select(Conversa).where(
                Conversa.id_conversa == request.conversa_id,
                Conversa.id_usuario == user.id_usuario
            )
            conversa = await db_session.scalar(stmt)
            
            if not conversa:
                raise HTTPException(status_code=404, detail="Conversa não encontrada")
            
            # Buscar histórico para contexto
            stmt_historico = select(HistoricoMensagem).where(
                HistoricoMensagem.id_conversa == request.conversa_id
            ).order_by(HistoricoMensagem.data_hora.desc()).limit(10)
            
            mensagens_anteriores = await db_session.scalars(stmt_historico)
            historico_list = list(reversed(list(mensagens_anteriores)))
            
            # Formar contexto do histórico
            if historico_list:
                historico_conversa = "\n".join([
                    f"{'Usuário' if msg.tipo == 'user' else 'Assistente'}: {msg.mensagem_texto}"
                    for msg in historico_list
                ])
        
        else:
            # Criar nova conversa
            titulo = request.message[:50] + "..." if len(request.message) > 50 else request.message
            conversa = Conversa(
                id_usuario=user.id_usuario,
                titulo=titulo
            )
            db_session.add(conversa)
            await db_session.flush()  # Para obter o ID
        
        # 2. Gerar resposta da IA
        resposta = await gerar_resposta(historico_conversa, request.message, user.nome)
        
        # 3. Determinar origem do contexto (simplificado)
        origem_contexto = "local"  # Você pode modificar gerar_resposta para retornar isso
        
        # 4. Salvar mensagem do usuário
        msg_usuario = HistoricoMensagem(
            id_conversa=conversa.id_conversa,
            id_usuario=user.id_usuario,
            mensagem_texto=request.message,
            tipo="user",
            origem_contexto="none"
        )
        db_session.add(msg_usuario)
        
        # 5. Salvar resposta da IA
        msg_assistant = HistoricoMensagem(
            id_conversa=conversa.id_conversa,
            id_usuario=user.id_usuario,
            mensagem_texto=resposta,
            tipo="assistant",
            origem_contexto=origem_contexto
        )
        db_session.add(msg_assistant)
        
        # 6. Atualizar última mensagem da conversa
        conversa.data_ultima_msg = msg_assistant.data_hora
        
        await db_session.commit()
        
        return ChatOut(
            response=resposta,
            conversa_id=conversa.id_conversa,
            origem_contexto=origem_contexto
        )
        
    except Exception as e:
        await db_session.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao processar mensagem: {str(e)}")


@router.post("/conversas", response_model=ConversaOut)
async def criar_conversa(
    request: ConversaCreate,
    user: LocalUserDep,
    auth_user: LoggedUserDep,
    db_session: SessionDep
) -> ConversaOut:
    """Criar nova conversa"""
    await validate_permission(auth_user, Permissions.CHAT_ACCESS)
    
    conversa = Conversa(
        id_usuario=user.id_usuario,
        titulo=request.titulo or "Nova Conversa"
    )
    db_session.add(conversa)
    await db_session.commit()
    await db_session.refresh(conversa)
    
    return conversa


@router.get("/conversas", response_model=ConversasListResponse)
async def listar_conversas(
    user: LocalUserDep,
    auth_user: LoggedUserDep,
    db_session: SessionDep
) -> ConversasListResponse:
    """Listar conversas do usuário"""
    await validate_permission(auth_user, Permissions.CHAT_ACCESS)
    
    stmt = select(Conversa).where(
        Conversa.id_usuario == user.id_usuario
    ).order_by(desc(Conversa.data_ultima_msg))
    
    conversas = await db_session.scalars(stmt)
    
    return ConversasListResponse(conversas=list(conversas))


@router.get("/conversas/{conversa_id}", response_model=ConversaComHistorico)
async def obter_conversa_com_historico(
    conversa_id: int,
    user: LocalUserDep,
    auth_user: LoggedUserDep,
    db_session: SessionDep
) -> ConversaComHistorico:
    """Obter conversa específica com histórico completo"""
    await validate_permission(auth_user, Permissions.CHAT_ACCESS)
    
    # Buscar conversa
    stmt = select(Conversa).where(
        Conversa.id_conversa == conversa_id,
        Conversa.id_usuario == user.id_usuario
    )
    conversa = await db_session.scalar(stmt)
    
    if not conversa:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    
    # Buscar histórico
    stmt_historico = select(HistoricoMensagem).where(
        HistoricoMensagem.id_conversa == conversa_id
    ).order_by(HistoricoMensagem.data_hora)
    
    historico = await db_session.scalars(stmt_historico)
    
    return ConversaComHistorico(
        conversa=conversa,
        historico=list(historico)
    )


@router.delete("/conversas/{conversa_id}")
async def deletar_conversa(
    conversa_id: int,
    user: LocalUserDep,
    auth_user: LoggedUserDep,
    db_session: SessionDep
):
    """Deletar conversa e todo seu histórico"""
    await validate_permission(auth_user, Permissions.CHAT_ACCESS)
    
    stmt = select(Conversa).where(
        Conversa.id_conversa == conversa_id,
        Conversa.id_usuario == user.id_usuario
    )
    conversa = await db_session.scalar(stmt)
    
    if not conversa:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    
    await db_session.delete(conversa)
    await db_session.commit()
    
    return {"message": "Conversa deletada com sucesso"}


# @router.post("/analyze-document")
# async def analyze_document(document_id: int):
#     """Endpoint para análise de documento com IA"""
#     pass

# @router.post("/generate-summary")
# async def generate_summary(text: str):
#     """Endpoint para gerar resumo usando IA"""
#     pass