import os
import asyncio
from concurrent.futures import ThreadPoolExecutor
from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from dotenv import load_dotenv

load_dotenv()
PASTA_BASE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'base_conhecimento')
if not os.path.exists(PASTA_BASE):
    os.makedirs(PASTA_BASE)

# Executor para tarefas pesadas em background
executor = ThreadPoolExecutor(max_workers=1)

def criar_db_sync():
    """Versão síncrona original - roda em thread separada"""
    print("Iniciando criação do banco de dados...")
    
    # Verificar se a pasta base existe
    if not os.path.exists(PASTA_BASE):
        print(f"Erro: Pasta {PASTA_BASE} não encontrada!")
        return False
    
    print(f"Pasta base encontrada: {PASTA_BASE}")
    
    try:
        documentos = carregar_documentos()
        print(f"Documentos carregados: {len(documentos)}")

        if not documentos:
            print("Nenhum documento encontrado para indexação. Verifique arquivos em 'app/base_conhecimento'.")
            return False

        chunks = dividir_chuncks(documentos)
        print(f"Chunks criados: {len(chunks)}")

        if not chunks:
            print("Nenhum chunk foi criado a partir dos documentos. Verifique o conteúdo dos PDFs e o splitter.")
            return False

        db = vetorizar_chuncks(chunks)
        if db is None:
            print("Erro na vetorização — verifique mensagens acima.")
            return False

        print("Banco de dados criado com sucesso!")
        return True
        
    except Exception as e:
        print(f"Erro durante criação do banco: {str(e)}")
        return False

async def criar_db_async():
    """Versão async - não bloqueia a aplicação"""
    print("Processando PDFs em background...")
    loop = asyncio.get_event_loop()
    
    # Roda a função pesada em thread separada
    result = await loop.run_in_executor(executor, criar_db_sync)
    
    if result:
        print("Indexação concluída! IA atualizada.")
    else:
        print("Erro na indexação.")
    
    return result

def criar_db():
    """Função original - use criar_db_async() nos endpoints"""
    return criar_db_sync()

def carregar_documentos():
    print("Carregando documentos...")
    # listar arquivos PDF na pasta para diagnóstico
    try:
        arquivos = [f for f in os.listdir(PASTA_BASE) if f.lower().endswith('.pdf')]
    except Exception as e:
        print(f"Erro ao listar pasta {PASTA_BASE}: {e}")
        return []

    if not arquivos:
        print("Nenhum arquivo .pdf encontrado em", PASTA_BASE)
        return []

    # mostrar nomes e tamanhos (debug)
    arquivos_info = []
    for f in arquivos:
        p = os.path.join(PASTA_BASE, f)
        try:
            size = os.path.getsize(p)
        except Exception:
            size = None
        arquivos_info.append((f, size))
    print("Arquivos detectados:")
    for name, size in arquivos_info:
        print(f" - {name} (size={size})")

    # checar cabeçalho simples para ver se é PDF válido
    valid_files = []
    for name, _ in arquivos_info:
        p = os.path.join(PASTA_BASE, name)
        try:
            with open(p, 'rb') as fh:
                header = fh.read(4)
            if header.startswith(b'%PDF'):
                valid_files.append(name)
            else:
                print(f"Aviso: arquivo {name} não tem cabeçalho PDF (%PDF) — pode estar corrompido ou em outro formato")
        except Exception as e:
            print(f"Erro ao abrir {name}: {e}")

    if not valid_files:
        print("Nenhum PDF válido detectado para carregar.")
        return []

    # Tentar carregar via PyPDFDirectoryLoader e capturar exceções para diagnóstico
    try:
        carregador = PyPDFDirectoryLoader(PASTA_BASE)
        documentos = carregador.load()
        return documentos
    except Exception as e:
        print(f"Erro ao carregar PDFs com PyPDFDirectoryLoader: {e}")
        print("Tentando carregar arquivos individualmente...")
        # fallback minimal: tente abrir cada arquivo e pular os que falham
        documentos = []
        for name in valid_files:
            path = os.path.join(PASTA_BASE, name)
            try:
                loader = PyPDFDirectoryLoader(path) if os.path.isdir(path) else PyPDFDirectoryLoader(os.path.dirname(path))
                docs = loader.load()
                # filtrar docs que têm source igual ao path
                for d in docs:
                    src = d.metadata.get('source') if hasattr(d, 'metadata') else None
                    if src and os.path.abspath(src) == os.path.abspath(path):
                        documentos.append(d)
            except Exception as e2:
                print(f"Erro ao tentar carregar {name}: {e2}")
        return documentos

def dividir_chuncks(documentos):
    print("Dividindo documentos em chunks...")
    
    separador_documentos = RecursiveCharacterTextSplitter(
        chunk_size=2000,
        chunk_overlap=500,
        length_function=len,
        add_start_index=True,
    )
    
    chuncks = separador_documentos.split_documents(documentos)
    return chuncks

def vetorizar_chuncks(chuncks):
    print("Vetorizando chunks...")
    
    CAMINHO_BANCO_DE_DADOS = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'banco_de_dados')
    
    # Criar pasta se não existir
    os.makedirs(CAMINHO_BANCO_DE_DADOS, exist_ok=True)
    
    if not chuncks:
        print("Lista de chunks vazia — pulando vetorização.")
        return None

    try:
        db = Chroma.from_documents(
            documents=chuncks,
            embedding=OpenAIEmbeddings(),
            persist_directory=CAMINHO_BANCO_DE_DADOS
        )
        print(f"Banco salvo em: {CAMINHO_BANCO_DE_DADOS}")
        return db
    except Exception as e:
        print(f"Erro ao criar vetores/Chroma: {e}")
        return None

if __name__ == "__main__":
    sucesso = criar_db()
    if sucesso:
        print("Banco de dados criado com sucesso!")
    else:
        print("Falha na criação do banco de dados!")
        exit(1)