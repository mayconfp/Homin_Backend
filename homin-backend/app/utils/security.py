"""
Utilitários de segurança para hash de senhas
"""
import bcrypt


def hash_password(password: str) -> str:
    """
    Gera hash bcrypt da senha
    
    Args:
        password: Senha em texto plano
        
    Returns:
        str: Hash bcrypt da senha
    """
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifica se senha corresponde ao hash
    
    Args:
        plain_password: Senha em texto plano
        hashed_password: Hash bcrypt da senha
        
    Returns:
        bool: True se senha é válida
    """
    password_bytes = plain_password.encode('utf-8')
    hashed_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password_bytes, hashed_bytes)
