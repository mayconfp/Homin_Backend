import os
from dotenv import load_dotenv
import openai
from langchain_core.output_parsers import StrOutputParser
from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma, chroma
from langchain_openai import OpenAIEmbeddings
from langchain.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from agno.tools.duckduckgo import DuckDuckGoTools
from agno.agent import Agent
from agno.models.openai import OpenAIChat
import dotenv

CAMINHO_BANCO_DE_DADOS = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'banco_de_dados')

load_dotenv()
OPENAI_API_KEY=os.getenv("OPENAI_API_KEY")

agente_classificador = Agent(
    model=OpenAIChat(id="gpt-4o"),
    instructions=""" 
    Você é um classificador de mensagens . 
    Classifique a mensagem do usuário em UMA das categorias:
    
    - SOCIAL: cumprimentos, agradecimentos, despedidas (oi, tchau, obrigado)
    - MEDICA: perguntas relacionadas à saúde, sintomas, tratamentos
    - GERAL: outras perguntas não relacionadas à saúde
    
    Responda APENAS com a categoria: SOCIAL, MEDICA ou GERAL""",
    markdown=False,
)

async def gerar_resposta(mensagens, entrada_usuario):
    # Classificar
    try:
        resposta = await agente_classificador.arun(entrada_usuario)
        categoria = resposta.content.strip().upper()
        print(f"✅ [DEBUG] Categoria classificada: '{categoria}'")
    except Exception:
        categoria = "GERAL"  # se a classificação falhar

    #  RETORNA para SOCIAL
    if categoria == "SOCIAL":
        return "Olá! Sou a Touch, como posso ajudar com saúde do homem?"

    # Inicializar contexto_final
    contexto_final = "Conhecimento geral sobre saúde do homem"

    # GERAL - sem busca web
    if categoria == "GERAL":
        contexto_final = "Você é a Touch, focada em saúde do homem. Responda educadamente redirecionando para tópicos de saúde."

    # MEDICA busca local e web se necessário
    elif categoria == "MEDICA":
        db = Chroma(persist_directory=CAMINHO_BANCO_DE_DADOS, embedding_function=OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY, model='text-embedding-3-small'))

        # Indica que a busca local está ocorrendo
        print("🔍 [DEBUG] Fazendo busca por similaridade...")
        resultados = db.similarity_search_with_relevance_scores(entrada_usuario, k=4)

        # Se não achou nada bom localmente busca web
        if len(resultados) == 0 or resultados[0][1] < -0.3:
            print("🌍 [DEBUG] Score baixo ou sem resultados - buscando na web...")
            try:
                agente_busca = Agent(
                    tools=[DuckDuckGoTools()],
                    instructions="Busque informações sobre saúde do homem"
                )
                resultado = await agente_busca.arun(entrada_usuario)
                resposta_busca = resultado.content
            except Exception:
                resposta_busca = ""
        else:
            resposta_busca = ""

        # Definir contexto baseado no que achou
        if resultados and resultados[0][1] >= -0.3:
            contexto_docs = "\n".join([doc[0].page_content for doc in resultados])
            contexto_final = f"Com base nos documentos internos sobre saúde do homem:\n{contexto_docs}"
        elif resposta_busca:
            contexto_final = f"Com base em informações encontradas na web:\n{resposta_busca}"

    # Gerar resposta final
    prompt = f"""Você é a Touch, assistente do Homin focada em saúde do homem.
    {contexto_final}

    Pergunta do usuário: {entrada_usuario}

    Responda de forma clara, amigável e cite a fonte das informações quando possível."""

    model = ChatOpenAI(model="gpt-4o", openai_api_key=OPENAI_API_KEY, temperature=0)
    resposta_final = await model.ainvoke(prompt)

    return resposta_final.content