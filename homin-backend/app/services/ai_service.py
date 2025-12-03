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
# Thresholds para estratégia híbrida
SCORE_EXCELENTE = -0.25  # >= -0.25: só base local (excelente)
SCORE_ACEITAVEL = -0.45  # >= -0.45: local + web (aceitável/médio) - ajustado para capturar mais conteúdo relevante
                         # < -0.45: só web (ruim)


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
    print("[DEBUG] Verificando relevância na base local...")
    db = None
    try:
        db = Chroma(
            persist_directory=CAMINHO_BANCO_DE_DADOS,
            embedding_function=OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY, model='text-embedding-3-small'),
        )
    except Exception as e:
        print(f"Falha ao inicializar Chroma/Chromadb: {e}")
        print("Continuando sem base local (fallback). Para restaurar, verifique chroma.sqlite3 ou reinstale chromadb/langchain-chroma")

    resultados_busca = []
    if db is not None:
        try:
            resultados_busca = db.similarity_search_with_relevance_scores(entrada_usuario, k=2)
        except Exception as e:
            print(f"Erro ao buscar similaridade na base local: {e}")
            resultados_busca = []

    # Verificar se há conteúdo relevante na base (Chroma usa distância cosine, valores menores = mais similares)
    # Usamos SCORE_ACEITAVEL para classificação inicial (aceita médio e excelente)
    tem_conteudo_relevante = False
    try:
        tem_conteudo_relevante = bool(resultados_busca and resultados_busca[0][1] >= SCORE_ACEITAVEL)
    except Exception:
        tem_conteudo_relevante = bool(resultados_busca)
    
    # Classificar com contexto sobre a base
    try:
        contexto_classificacao = ""
        if tem_conteudo_relevante:
            contexto_classificacao = "\n\nNOTA: Há documentos relevantes na base de conhecimento para esta pergunta."
        
        prompt_classificacao = f"{entrada_usuario}{contexto_classificacao}"
        resposta = await agente_classificador.arun(prompt_classificacao)
        categoria = resposta.content.strip().upper()
        print(f"[DEBUG] Categoria classificada: '{categoria}' (base relevante: {tem_conteudo_relevante})")
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
        return resposta_social.content, "general"

    # Inicializar contexto_final e origem
    contexto_final = "Conhecimento geral sobre saúde do homem"
    origem_contexto = "general"

    # GERAL - mas se tem conteúdo relevante trata como MEDICA
    if categoria == "GERAL" and not tem_conteudo_relevante:
        contexto_final = "Você é a Touch, focada em saúde do homem. Responda educadamente redirecionando para tópicos de saúde."

    # MEDICA ou GERAL com conteúdo relevante - busca local e web se necessário
    else:
        # Usar os resultados já obtidos
        print("[DEBUG] Fazendo busca detalhada por similaridade...")
        resultados = []
        if db is not None:
            try:
                resultados = db.similarity_search_with_relevance_scores(entrada_usuario, k=4)
            except Exception as e:
                print(f"Erro ao buscar similaridade detalhada: {e}")
                resultados = []

        if resultados:
            try:
                print(f"[DEBUG] Scores encontrados: {[round(r[1], 3) for r in resultados]}")
            except Exception:
                pass

        # Aplicar estratégia híbrida de busca (local + web)
        top_score = resultados[0][1] if resultados else None
        print(f"[DEBUG] Top score: {top_score} | Excelente: {SCORE_EXCELENTE} | Aceitável: {SCORE_ACEITAVEL}")
        
        resposta_busca = ""
        usar_local = False
        
        if resultados and top_score is not None:
            if top_score >= SCORE_EXCELENTE:
                # Excelente: só base local
                usar_local = True
                usar_web = False
                print("✅ [DEBUG] Score excelente - usando APENAS base local")
            elif top_score >= SCORE_ACEITAVEL:
                # Médio: local + web (híbrido)
                usar_local = True
                usar_web = True
                print("⚡ [DEBUG] Score médio - usando base local + busca web (híbrido)")
            else:
                # Ruim: só web
                usar_local = False
                usar_web = True
                print("🌍 [DEBUG] Score ruim - usando APENAS busca web")
        else:
            # Sem resultados: só web
            usar_web = True
            print("🌍 [DEBUG] Sem resultados locais - buscando na web")
        
        # Executar busca web se necessário
        if usar_web:
            try:
                agente_busca = Agent(
                    tools=[DuckDuckGoTools()],
                    instructions="Busque informações confiáveis sobre saúde do homem em português"
                )
                resultado = await agente_busca.arun(entrada_usuario)
                resposta_busca = resultado.content
                print(f"✅ [DEBUG] Busca web concluída! Tamanho: {len(resposta_busca)} chars")
            except Exception as e:
                print(f"❌ [DEBUG] Erro na busca web: {e}")
                resposta_busca = ""
        
        # Definir contexto final combinando fontes
        if usar_local and resposta_busca:
            # Híbrido: local + web
            contexto_docs = "\n".join([doc[0].page_content for doc in resultados[:2]])
            contexto_final = f"""INFORMAÇÕES DA BASE LOCAL:
{contexto_docs}

INFORMAÇÕES COMPLEMENTARES DA WEB:
{resposta_busca}"""
            origem_contexto = "hybrid"
            print(f"🔄 [DEBUG] Usando contexto HÍBRIDO (local + web, score: {top_score:.3f})")
        elif usar_local:
            # Só local
            # Só local
            contexto_docs = "\n".join([doc[0].page_content for doc in resultados[:3]])
            contexto_final = f"Com base nos documentos internos:\n{contexto_docs}"
            origem_contexto = "local"
            print(f"📄 [DEBUG] Usando APENAS base local (score: {top_score:.3f})")
        elif resposta_busca:
            # Só web
            contexto_final = f"Com base em informações encontradas na web:\n{resposta_busca}"
            origem_contexto = "web"
            print("🌐 [DEBUG] Usando APENAS busca web")
        else:
            # Fallback: conhecimento geral da IA
            origem_contexto = "general"
            print("💭 [DEBUG] Sem contexto específico - usando conhecimento geral da IA")

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

    Responda de forma clara, amigável e natural, considerando o contexto da conversa anterior. Use o nome do usuário quando apropriado para personalizar a resposta. Seja objetiva e direta, sem mencionar repetidamente suas fontes de informação."""

    model = ChatOpenAI(model="gpt-4o", openai_api_key=OPENAI_API_KEY, temperature=0)
    resposta_final = await model.ainvoke(prompt)

    # Retornar resposta e origem do contexto
    return resposta_final.content, origem_contexto