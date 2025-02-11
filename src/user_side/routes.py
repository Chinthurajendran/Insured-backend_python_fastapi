from fastapi import APIRouter,Depends,status
from .schemas import*
from sqlmodel.ext.asyncio.session import AsyncSession
from src.db.database import get_session
from .service import UserService
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse
from src.utils import create_access_token,decode_token,verify_password
from datetime import timedelta


auth_router = APIRouter()
user_service = UserService()
REFRESH_TOKEN_EXPIRY = 2

@auth_router.post("/signup",response_model = UserModel,status_code= status.HTTP_201_CREATED )
async def create_user_account(user_data:UserCreate,session:AsyncSession = Depends(get_session)):

    email = user_data.email
    username = user_data.username
    user_exists_with_email = await user_service.exist_email(email,session)
    user_exists_with_username = await user_service.exist_username(username,session)
    if user_exists_with_email:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User with email already exists")
    if user_exists_with_username:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User with username already exists")
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

    if user is not None:
        password_vaild = verify_password(password,user.password)

        if password_vaild:
            access_token = create_access_token(
                user_data={
                    'email':user.email,
                    'user_id':str(user.user_id)
                }
            )

            refresh_token = create_access_token(
                user_data={
                    'email':user.email,
                    'user_id':str(user.user_id)
                },
                refresh=True,
                expiry=timedelta(days=REFRESH_TOKEN_EXPIRY)
            )
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "message":"Login succesfull",
                    "access_token":access_token,
                    "refresh_token":refresh_token,
                    "user_id":str(user.user_id),
                    "user_name":str(user.username)
                }
            )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Invalid Email  or Password"
    )