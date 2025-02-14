from passlib.context import CryptContext
from datetime import timedelta,datetime
import jwt
from src.config import Config
import uuid
import logging
from pathlib import Path
import random


password_context= CryptContext(
    schemes=['bcrypt']
)

def generate_passwd_hash(password):
    hash = password_context.hash(password)
    return hash

def verify_password(password,hash):
    return password_context.verify(password,hash)

ACCESS_TOKEN_EXPIRY = 3600

def create_access_token(user_data:dict,expiry:timedelta=None,refresh :bool= False):
    payload = {}

    payload['user'] = user_data
    payload['exp'] = datetime.now() + (expiry if expiry is not None else timedelta(seconds=ACCESS_TOKEN_EXPIRY))
    payload['jti'] = str(uuid.uuid4())
    payload['refresh'] = refresh

    token = jwt.encode(
        payload=payload,
        key=Config.JWT_SECRET,
        algorithm=Config.JWT_ALOGRITHM

    )
    return token

def decode_token(token:str):
    try:
        token_data = jwt.decode(
            jwt = token,
            key = Config.JWT_SECRET,
            algorithms = Config.JWT_ALOGRITHM
        )
        return token_data
    except jwt.PyJWTError as e:
        logging.exception(e)
        return None
    

UPLOAD_DIR = Path("D:/BROTOTYPE BOX/TASK/Week 23 1.0/Project 5.0/frontend/src/assets/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

def random_code():
    return random.randint(100000, 999999)