from datetime import datetime
import uuid
from sqlalchemy import (
    Column, String, Text, DateTime, ForeignKey, BigInteger, Boolean
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from .config import Base

class Usuario(Base):
    __tablename__ = "usuarios"
    id_usuario = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    auth0_sub = Column(String(255), unique=True, nullable=True)  # Subject do Auth0 (google-oauth2|xxxx)
    role = Column(String(20), nullable=False, default="user")
    data_cadastro = Column(DateTime, default=datetime.utcnow)

    # relationships
    conversas = relationship("Conversa", back_populates="usuario", cascade="all, delete-orphan")
    documentos = relationship("Documento", back_populates="usuario", cascade="all, delete-orphan")
    historicos = relationship("HistoricoMensagem", back_populates="usuario")

class Documento(Base):
    __tablename__ = "documentos"
    id_documento = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_usuario = Column(UUID(as_uuid=True), ForeignKey("usuarios.id_usuario"), nullable=False)
    nome_arquivo = Column(String(255))
    tipo_documento = Column(String(100))
    data_criacao = Column(DateTime, default=datetime.utcnow)

    usuario = relationship("Usuario", back_populates="documentos")
    historicos = relationship("HistoricoMensagem", back_populates="documento")

class Conversa(Base):
    __tablename__ = "conversas"
    id_conversa = Column(BigInteger, primary_key=True, autoincrement=True)
    id_usuario = Column(UUID(as_uuid=True), ForeignKey("usuarios.id_usuario"), nullable=False)
    titulo = Column(String(255))
    data_inicio = Column(DateTime, default=datetime.utcnow)
    data_ultima_msg = Column(DateTime, nullable=True)

    usuario = relationship("Usuario", back_populates="conversas")
    historicos = relationship("HistoricoMensagem", back_populates="conversa", cascade="all, delete-orphan")

class HistoricoMensagem(Base):
    __tablename__ = "historico_mensagem"
    id_historico = Column(BigInteger, primary_key=True, autoincrement=True)
    id_conversa = Column(BigInteger, ForeignKey("conversas.id_conversa"), nullable=False)
    id_usuario = Column(UUID(as_uuid=True), ForeignKey("usuarios.id_usuario"), nullable=False)
    id_documento = Column(UUID(as_uuid=True), ForeignKey("documentos.id_documento"), nullable=True)
    mensagem_texto = Column(Text, nullable=False)
    tipo = Column(String(20))  # 'user' ou 'admin' / ou gerar enum
    origem_contexto = Column(String(50))  # 'local','web','none', etc
    data_hora = Column(DateTime, default=datetime.utcnow)

    conversa = relationship("Conversa", back_populates="historicos")
    usuario = relationship("Usuario", back_populates="historicos")
    documento = relationship("Documento", back_populates="historicos")