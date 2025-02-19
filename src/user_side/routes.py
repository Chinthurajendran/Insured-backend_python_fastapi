from fastapi import APIRouter,Depends,status
from .schemas import*
from sqlmodel.ext.asyncio.session import AsyncSession
from src.db.database import get_session
from .service import UserService
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse
from src.utils import create_access_token,decode_token,verify_password
from datetime import timedelta
from .dependencies import*
from .models import*
from sqlmodel import select
from uuid import UUID
from .dependencies import *
from google.oauth2 import id_token
from google.auth.transport import requests
from jose import JWTError
import requests


auth_router = APIRouter()
user_service = UserService()
access_token_bearer = AccessTokenBearer()
REFRESH_TOKEN_EXPIRY = 2
GOOGLE_CLIENT_ID = "270374642053-gvj2j07247e2h96gbd929oh12li1rs2l.apps.googleusercontent.com"


@auth_router.post("/signup",response_model = UserModel,status_code= status.HTTP_201_CREATED )
async def create_user_account(user_data:UserCreate,session:AsyncSession = Depends(get_session)):

    email = user_data.email.lower()  
    username = user_data.username.lower()
    user_exists_with_email = await user_service.exist_email(email,session)
    user_exists_with_username = await user_service.exist_username(username,session)
    if user_exists_with_email:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Email already exists")
    if user_exists_with_username:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Username already exists")
    if user_data.password != user_data.confirm_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Passwords do not match")
    
    new_user = await user_service.create_user(user_data,session)
    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={
            "message": "Registration successful! Please log in.",
        }
    )


@auth_router.post('/login')
async def login_user(login_data:UserLoginModel,session:AsyncSession = Depends(get_session)):
    email = login_data.email
    password = login_data.password

    user = await user_service.get_user_by_email(email,session)

    if user.block_status: 
        raise HTTPException(status_code=404, detail="User is blocked")

    if user is not None:
        password_vaild = verify_password(password,user.password)

        if password_vaild:
            user_access_token = create_access_token(
                user_data={
                    'email':user.email,
                    'user_id':str(user.user_id),
                    'user_role' :str(user.role)
                }
            )

            user_refresh_token = create_access_token(
                user_data={
                    'user_email':user.email,
                    'user_id':str(user.user_id),
                    'user_role' :str(user.role)
                },
                refresh=True,
                expiry=timedelta(days=REFRESH_TOKEN_EXPIRY)
            )
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "message":"Login succesfull",
                    "user_access_token":user_access_token,
                    "user_refresh_token":user_refresh_token,
                    "user_id":str(user.user_id),
                    "user_name":str(user.username),
                    'user_role' :str(user.role)
                }
            )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Invalid Email  or Password"
    )




def verify_google_token(token: str):
    # Send request to Google to verify the token
    response = requests.get(f'https://oauth2.googleapis.com/tokeninfo?id_token={token}')

    if response.status_code != 200:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token")
    
    token_info = response.json()
    print(token_info['aud'])

    if token_info['aud'] != GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token's audience doesn't match")
    return token_info


@auth_router.post("/google-login")
async def google_login(auth_data: GoogleAuthModel, session: AsyncSession = Depends(get_session)):
    try:

        idinfo = verify_google_token(auth_data.token)
        
        if "email" not in idinfo:
            raise HTTPException(status_code=400, detail="Invalid Google token")

        email = idinfo["email"]
        user = await user_service.get_user_by_email(email, session)

        if not user:
            raise HTTPException(status_code=404, detail="User not found, please register")

        if user.block_status:
            raise HTTPException(status_code=403, detail="User is blocked")

        user_access_token = create_access_token(
            user_data={
                "email": user.email,
                "user_id": str(user.user_id),
                "user_role": str(user.role),
            }
        )

        user_refresh_token = create_access_token(
            user_data={
                "user_email": user.email,
                "user_id": str(user.user_id),
                "user_role": str(user.role),
            },
            refresh=True,
            expiry=timedelta(days=REFRESH_TOKEN_EXPIRY),
        )

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "message": "Login successful",
                "user_access_token": user_access_token.decode() if isinstance(user_access_token, bytes) else user_access_token,
                "user_refresh_token": user_refresh_token.decode() if isinstance(user_refresh_token, bytes) else user_refresh_token,
                "user_id": str(user.user_id),
                "user_name": str(user.username),
                "user_role": str(user.role),
            },
        )

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid Google token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Could not validate credentials")
    except Exception as e:
        print('Exception:', e)
        raise HTTPException(status_code=500, detail="Internal server error")


@auth_router.get("/user_refresh_token")
async def get_new_access_token(token_details: dict = Depends(RefreshTokenBearer())):
    expiry_timestamp = token_details["exp"]
    if datetime.fromtimestamp(expiry_timestamp) > datetime.now():
        new_access_token = create_access_token(
            user_data=token_details['user']
        )

        return JSONResponse(content={"access_token": new_access_token})
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid or expired token")

@auth_router.put("/user_logout/{user_id}")
async def logout_agent(
    user_id: UUID,
    session: AsyncSession = Depends(get_session),
    user_details=Depends(access_token_bearer),
):
    result = await session.execute(select(usertable).where(usertable.user_id == user_id))
    user = result.scalars().first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    await session.commit()
    
    return JSONResponse(status_code=200, content={"message": "User logged out successfully."})