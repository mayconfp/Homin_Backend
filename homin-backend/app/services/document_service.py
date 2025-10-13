import os
from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from dotenv import load_dotenv

load_dotenv()
PASTA_BASE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'base_conhecimento')
if not os.path.exists(PASTA_BASE):
    os.makedirs(PASTA_BASE)

def criar_db():
    print("🚀 Iniciando criação do banco de dados...")
    
    # Verificar se a pasta base existe
    if not os.path.exists(PASTA_BASE):
        print(f"❌ Erro: Pasta {PASTA_BASE} não encontrada!")
        return False
    
    print(f"✅ Pasta base encontrada: {PASTA_BASE}")
    
    try:
        documentos = carregar_documentos()
        print(f"✅ Documentos carregados: {len(documentos)}")
        
        chunks = dividir_chuncks(documentos)
        print(f"✅ Chunks criados: {len(chunks)}")
        
        db = vetorizar_chuncks(chunks)
        print("✅ Banco de dados criado com sucesso!")
        return True
        
    except Exception as e:
        print(f"❌ Erro durante criação do banco: {str(e)}")
        return False

def carregar_documentos():
    print("📄 Carregando documentos...")
    carregador = PyPDFDirectoryLoader(PASTA_BASE)
    documentos = carregador.load() 
    return documentos

def dividir_chuncks(documentos):
    print("✂️ Dividindo documentos em chunks...")
    
    separador_documentos = RecursiveCharacterTextSplitter(
        chunk_size=2000,
        chunk_overlap=500,
        length_function=len,
        add_start_index=True,
    )
    
    chuncks = separador_documentos.split_documents(documentos)
    return chuncks

def vetorizar_chuncks(chuncks):
    print("🔍 Vetorizando chunks...")
    
    CAMINHO_BANCO_DE_DADOS = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'banco_de_dados')
    
    # Criar pasta se não existir
    os.makedirs(CAMINHO_BANCO_DE_DADOS, exist_ok=True)
    
    db = Chroma.from_documents(
        documents=chuncks,
        embedding=OpenAIEmbeddings(),
        persist_directory=CAMINHO_BANCO_DE_DADOS
    )
    
    print(f"✅ Banco salvo em: {CAMINHO_BANCO_DE_DADOS}")
    return db

if __name__ == "__main__":
    sucesso = criar_db()
    if sucesso:
        print("🎉 Banco de dados criado com sucesso!")
    else:
        print("💥 Falha na criação do banco de dados!")
        exit(1)