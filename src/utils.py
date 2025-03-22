from passlib.context import CryptContext
from datetime import timedelta,datetime
import jwt
from src.config import Config
import uuid
import logging
from pathlib import Path
import random
from fastapi.exceptions import HTTPException
from fastapi import Request, status
import pytz
import jwt
import logging
from jwt.exceptions import ExpiredSignatureError, DecodeError, InvalidTokenError

password_context= CryptContext(
    schemes=['bcrypt']
)

def generate_passwd_hash(password):
    hash = password_context.hash(password)
    return hash

def verify_password(password,hash):
    return password_context.verify(password,hash)

# ACCESS_TOKEN_EXPIRY = 3600
ACCESS_TOKEN_EXPIRY = 60

ist = pytz.timezone("Asia/Kolkata")

def create_access_token(user_data: dict, expiry: timedelta = None, refresh: bool = False):
    # Get the current UTC time
    utc_time = datetime.utcnow().replace(tzinfo=pytz.utc)

    # Convert UTC time to IST
    local_time = utc_time.astimezone(ist)

    # Compute expiration time correctly
    expiration_time_ist = local_time + (expiry if expiry else timedelta(seconds=ACCESS_TOKEN_EXPIRY))

    payload = {}
    payload['user'] = user_data
    payload['exp'] = expiration_time_ist.timestamp()
    payload['jti'] = str(uuid.uuid4())
    payload['refresh'] = refresh

    print("Correct JWT Payload:", payload)

    token = jwt.encode(
        payload=payload,
        key=Config.JWT_SECRET,
        algorithm=Config.JWT_ALOGRITHM
    )

    return token


def decode_token(token: str):
    try:
        token_data = jwt.decode(
            token,
            key=Config.JWT_SECRET,
            algorithms=[Config.JWT_ALOGRITHM]  # Fixed typo
        )
        return token_data
    except ExpiredSignatureError:
        logging.exception("Token has expired.")
        return None
    except (DecodeError, InvalidTokenError) as e:
        logging.exception(f"Invalid token: {e}")
        return None


    

UPLOAD_DIR = Path("D:/BROTOTYPE BOX/TASK/Week 23 1.0/Project 5.0/frontend/src/assets/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

def random_code():
    return random.randint(100000, 999999)