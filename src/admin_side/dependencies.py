from fastapi.security import HTTPBearer
from fastapi import Request,status
from fastapi.security.http import HTTPAuthorizationCredentials
from src.utils import decode_token
from fastapi.exceptions import HTTPException
from typing import Optional

class AccessTokenBearer(HTTPBearer):
    
    def __init__(self,auto_error = True):
        super().__init__(auto_error = auto_error)

    async def __call__(self, request: Request) -> Optional[HTTPAuthorizationCredentials]:
        creds= await super().__call__(request)

        token = creds.credentials
        token_data=decode_token(token)

        if not self.token_valid(token):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid or  expired token"
            )
        if 'refresh' in token_data and token_data['refresh']:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Please provide an access token"
            )

        return token_data
    

    def token_valid(self,token:str):
        token_data=decode_token(token)

        if token_data is not None:
            return True
        else:
            return False

