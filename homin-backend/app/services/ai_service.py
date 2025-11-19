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


def extrair_primeiro_nome(nome: str | None) -> str | None:
    """Retorna o primeiro nome formatado (Title-case) ou None se não houver nome."""
    if not nome:
        return None
    # Remove espaços extras e pega o primeiro token
    primeiro = nome.strip().split()[0]
    # Normaliza: transforma em Title case para respostas mais naturais
    try:
        return primeiro.title()
    except Exception:
        return primeiro

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

async def gerar_resposta(historico_conversa, entrada_usuario, nome_usuario=None):
    # Primeiro, fazer uma busca rápida na base para ver se há conteúdo relevante
    print("🔍 [DEBUG] Verificando relevância na base local...")
    db = None
    try:
        db = Chroma(
            persist_directory=CAMINHO_BANCO_DE_DADOS,
            embedding_function=OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY, model='text-embedding-3-small'),
        )
    except Exception as e:
        print(f"⚠️ Falha ao inicializar Chroma/Chromadb: {e}")
        print("⚠️ Continuando sem base local (fallback). Para restaurar, verifique chroma.sqlite3 ou reinstale chromadb/langchain-chroma")

    resultados_busca = []
    if db is not None:
        try:
            resultados_busca = db.similarity_search_with_relevance_scores(entrada_usuario, k=2)
        except Exception as e:
            print(f"⚠️ Erro ao buscar similaridade na base local: {e}")
            resultados_busca = []

    # Verificar se há conteúdo relevante na base (Chroma usa distância cosine, valores menores = mais similares)
    tem_conteudo_relevante = resultados_busca and resultados_busca[0][1] > -0.5
    
    # Classificar com contexto sobre a base
    try:
        contexto_classificacao = ""
        if tem_conteudo_relevante:
            contexto_classificacao = "\n\nNOTA: Há documentos relevantes na base de conhecimento para esta pergunta."
        
        prompt_classificacao = f"{entrada_usuario}{contexto_classificacao}"
        resposta = await agente_classificador.arun(prompt_classificacao)
        categoria = resposta.content.strip().upper()
        print(f"✅ [DEBUG] Categoria classificada: '{categoria}' (base relevante: {tem_conteudo_relevante})")
    except Exception:
        categoria = "MEDICA" if tem_conteudo_relevante else "GERAL"  # Se tem conteúdo relevante, força MEDICA

    #  Para SOCIAL, usar modelo com contexto específico
    if categoria == "SOCIAL":
        historico_texto = ""
        if historico_conversa:
            historico_texto = f"Histórico da conversa:\n{historico_conversa}\n"
        
        primeiro_nome = extrair_primeiro_nome(nome_usuario)
        nome_texto = f"Informação do usuário: O primeiro nome do usuário é {primeiro_nome}.\n" if primeiro_nome else ""
        
        prompt_social = f"""Você é a Touch, assistente do Homin focada em saúde do homem.
        
        {nome_texto}
        {historico_texto}
        
        O usuário disse: {entrada_usuario}  
        
        Responda de forma amigável e natural ao cumprimento/agradecimento/despedida, considerando o contexto da conversa. Use o primeiro nome do usuário quando apropriado para personalizar a resposta. Se apropriado, ofereça ajuda com temas de saúde masculina. Seja calorosa mas mantenha o foco profissional."""

        model = ChatOpenAI(model="gpt-4o", openai_api_key=OPENAI_API_KEY, temperature=0.3)
        resposta_social = await model.ainvoke(prompt_social)
        return resposta_social.content

    # Inicializar contexto_final
    contexto_final = "Conhecimento geral sobre saúde do homem"

    # GERAL - mas se tem conteúdo relevante trata como MEDICA
    if categoria == "GERAL" and not tem_conteudo_relevante:
        contexto_final = "Você é a Touch, focada em saúde do homem. Responda educadamente redirecionando para tópicos de saúde."

    # MEDICA ou GERAL com conteúdo relevante - busca local e web se necessário
    else:
        # Usar os resultados já obtidos
        print("🔍 [DEBUG] Fazendo busca detalhada por similaridade...")
        resultados = []
        if db is not None:
            try:
                resultados = db.similarity_search_with_relevance_scores(entrada_usuario, k=4)
            except Exception as e:
                print(f"⚠️ Erro ao buscar similaridade detalhada: {e}")
                resultados = []

        if resultados:
            try:
                print(f"🔍 [DEBUG] Scores encontrados: {[round(r[1], 3) for r in resultados]}")
            except Exception:
                pass

        # Se não achou nada bom localmente busca web (Chroma: valores menores = mais similares)
        if len(resultados) == 0 or resultados[0][1] > -0.3:
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

        # Definir contexto baseado no que achou (Chroma: valores menores = mais similares)
        if resultados and resultados[0][1] <= -0.4:
            contexto_docs = "\n".join([doc[0].page_content for doc in resultados])
            contexto_final = f"Com base nos documentos internos:\n{contexto_docs}"
            print("✅ [DEBUG] Usando documentos da base local!")
        elif resposta_busca:
            contexto_final = f"Com base em informações encontradas na web:\n{resposta_busca}"
            print("🌍 [DEBUG] Usando busca web!")

    # Gerar resposta final
    historico_texto_final = ""
    if historico_conversa:
        historico_texto_final = f"Histórico da conversa:\n{historico_conversa}\n"

    primeiro_nome_final = extrair_primeiro_nome(nome_usuario)
    nome_texto_final = f"Informação do usuário: O primeiro nome do usuário é {primeiro_nome_final}.\n" if primeiro_nome_final else ""
    
    prompt = f"""Você é a Touch, assistente do Homin focada em saúde do homem.
    
    {nome_texto_final}
    {historico_texto_final}
    
    {contexto_final}

    Pergunta do usuário: {entrada_usuario}

    Responda de forma clara, amigável, considerando o contexto da conversa anterior. Use o nome do usuário quando apropriado para personalizar a resposta. Cite a fonte das informações quando possível."""

    model = ChatOpenAI(model="gpt-4o", openai_api_key=OPENAI_API_KEY, temperature=0)
    resposta_final = await model.ainvoke(prompt)

    return resposta_final.content