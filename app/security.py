# Utilitários de segurança
# Funções para autenticação, autorização, criptografia, etc.

# Aqui ficam as funções relacionadas à segurança:
# - Hash de senhas
# - Geração e validação de tokens JWT
# - Middleware de autenticação
# - Validação de permissões

# Exemplo:
# from passlib.context import CryptContext
# from jose import JWTError, jwt
# from datetime import datetime, timedelta

# pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# def verify_password(plain_password: str, hashed_password: str) -> bool:
#     """Verifica se a senha está correta"""
#     return pwd_context.verify(plain_password, hashed_password)

# def get_password_hash(password: str) -> str:
#     """Gera hash da senha"""
#     return pwd_context.hash(password)

# def create_access_token(data: dict, expires_delta: timedelta = None):
#     """Cria token JWT de acesso"""
#     to_encode = data.copy()
#     if expires_delta:
#         expire = datetime.utcnow() + expires_delta
#     else:
#         expire = datetime.utcnow() + timedelta(minutes=15)
#     to_encode.update({"exp": expire})
#     encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
#     return encoded_jwt

# def verify_token(token: str):
#     """Verifica e decodifica token JWT"""
#     try:
#         payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
#         return payload
#     except JWTError:
#         return None