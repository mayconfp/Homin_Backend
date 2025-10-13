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
from agno.agent import Agent
from agno.tools.duckduckgo import DuckDuckGoTools
import dotenv

CAMINHO_BANCO_DE_DADOS = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'banco_de_dados')

load_dotenv()
OPENAI_API_KEY=os.getenv("OPENAI_API_KEY")

async def gerar_resposta(mensagens, entrada_usuario):

    db = Chroma(persist_directory=CAMINHO_BANCO_DE_DADOS, embedding_function=OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY, model='text-embedding-3-small'))

        # Busca similaridade
    resultados = db.similarity_search_with_relevance_scores(entrada_usuario, k=4) # o k é a qtd dos resultadados que vc qr qt mais aumenta mais contexto ele vai usar

        # Para scores negativos, consideramos relevante se for maior que -0.25
        # Valores mais próximos de 0 indicam maior relevância
    if len(resultados) == 0 or resultados[0][1] < -0.25:
        print("Não conseguiu encontrar nenhuma informação relevante na base")
    else:
            print(f"Informações relevantes encontradas! Score: {resultados[0][1]}")

    textos_resultado = []
    if len(resultados) > 0:
        for resultado in resultados:
            texto = resultado[0].page_content
            textos_resultado.append(texto)

        base_conhecimentos = "\n".join(textos_resultado) if textos_resultado else "nenhuma informação encontrada"

        # Busca web se não tiver informações locais suficientes
        busca_web = ""
        if len(resultados) == 0 or resultados[0][1] < -0.25:
            print("Buscando informações na web...")
            try:
                agente_busca = Agent(
                    tools=[DuckDuckGoTools(modifier="Saúde do homem")],
                    instructions="Busque informações relevantes na web sobre a Saúde do homem"
                )
                resultado_busca = agente_busca.run(f'{entrada_usuario} Saúde do homem')
                busca_web = f"Informações da web: {resultado_busca.content}"
            except Exception as e:
                print(f"Erro ao realizar busca na web: {e}")
                busca_web = ""
        else:
            print("Informações locais suficientes encontradas, não buscando na web")

        # Define contexto final
        if base_conhecimentos:
            contexto_final = f"Informações dos documentos internos: {base_conhecimentos}"
        elif busca_web:
            contexto_final = f"Informações encontradas na web: {busca_web}"
        else:
            contexto_final = "Informações gerais sobre saúde do homem."

        prompt_resposta_da_ia = f"""
            Você é a Touch, assistente do Homin, que são estudantes da uninassau que está desenvolvendo dicas de saúde do homem.
            
            {contexto_final}
            
            Responda à pergunta: {entrada_usuario}
            
            IMPORTANTE: Sempre cite a origem das informações quando possível (documentos internos ou informações públicas).
            
            Se não houver informações específicas, seja amigável e ofereça ajuda.
            """


        model = ChatOpenAI(
            openai_api_key=OPENAI_API_KEY,
            model='gpt-4o',
            temperature=0.5,
            max_tokens=2000
        )

        # vai receber o prompt e todas as mensagens usuário + IA para manter contexto
        resposta = await model.ainvoke([prompt_resposta_da_ia]+mensagens)
        return resposta.content
