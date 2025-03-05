from fastapi.security import HTTPBearer
from fastapi import Request, status
from fastapi.security.http import HTTPAuthorizationCredentials
from src.utils import decode_token
from fastapi.exceptions import HTTPException
from typing import Optional
import jwt


class TokenBearer(HTTPBearer):

    def __init__(self, auto_error=True):
        super().__init__(auto_error=auto_error)

    async def __call__(self, request: Request) -> Optional[HTTPAuthorizationCredentials]:
        creds = await super().__call__(request)
        token = creds.credentials

        print("qqqqqqqqqqqqqqqqqq",token)
        token_data = decode_token(token)
        print("wwwwwwwwwwwwwwwwwww",token_data)
        
        if not self.token_valid(token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or  expired token"
            ) 

        self.verify_token_data(token_data)
        self.check_user_role(token_data)

        return token_data

    def token_valid(self, token: str):
        token_data = decode_token(token)
        return True if token_data is not None else False

    def verify_token_data(self, token_data):
        raise NotImplementedError(
            "Please Override this method in child classes")
    
    def check_user_role(self, token_data: dict):
        user_data = token_data.get("user", {})
        user_role = user_data.get("user_role")

        if user_role != "user":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied! Only user are allowed."
            )
    
    # def decode_token(token: str):
    #         try:
    #             return jwt.decode(token, 'your_secret_key', algorithms=['HS256'])
    #         except jwt.ExpiredSignatureError:
    #             raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token has expired")
    #         except jwt.InvalidTokenError:
    #             raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid token")

class AccessTokenBearer(TokenBearer):
    def verify_token_data(self, token_data: dict):
        if token_data and token_data['refresh']:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Please provide an access token"
            )


class RefreshTokenBearer(TokenBearer):
    def verify_token_data(self, token_data: dict):
        print("ttttttttttttttttttttt",token_data)
        if token_data and not token_data['refresh']:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Please provide an refresh token"
            )
