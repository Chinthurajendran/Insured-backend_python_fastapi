from fastapi import APIRouter, Depends, status,Form,UploadFile, File
from .schemas import *
from sqlmodel.ext.asyncio.session import AsyncSession
from src.db.database import get_session
from .service import UserService
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse
from src.utils import create_access_token, decode_token, verify_password
from datetime import timedelta
from .dependencies import *
from .models import *
from sqlmodel import select
from uuid import UUID
from .dependencies import *
from google.oauth2 import id_token
from google.auth.transport import requests
from jose import JWTError
import requests
from typing import Optional
from typing import List
from src.admin_side.models import policytable
from math import pow


auth_router = APIRouter()
user_service = UserService()
access_token_bearer = AccessTokenBearer()
REFRESH_TOKEN_EXPIRY = 2
GOOGLE_CLIENT_ID = "270374642053-gvj2j07247e2h96gbd929oh12li1rs2l.apps.googleusercontent.com"


@auth_router.post("/signup", response_model=UserModel, status_code=status.HTTP_201_CREATED)
async def create_user_account(user_data: UserCreate, session: AsyncSession = Depends(get_session)):

    email = user_data.email.lower()
    username = user_data.username.lower()
    user_exists_with_email = await user_service.exist_email(email, session)
    user_exists_with_username = await user_service.exist_username(username, session)
    if user_exists_with_email:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Email already exists")
    if user_exists_with_username:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Username already exists")
    if user_data.password != user_data.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Passwords do not match")

    new_user = await user_service.create_user(user_data, session)
    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={
            "message": "Registration successful! Please log in.",
        }
    )


@auth_router.post('/login')
async def login_user(login_data: UserLoginModel, session: AsyncSession = Depends(get_session)):
    email = login_data.email
    password = login_data.password

    user = await user_service.get_user_by_email(email, session)

    if user.block_status:
        raise HTTPException(status_code=404, detail="User is blocked")

    if user is not None:
        password_vaild = verify_password(password, user.password)

        if password_vaild:
            user_access_token = create_access_token(
                user_data={
                    'email': user.email,
                    'user_id': str(user.user_id),
                    'user_role': str(user.role)
                }
            )

            user_refresh_token = create_access_token(
                user_data={
                    'user_email': user.email,
                    'user_id': str(user.user_id),
                    'user_role': str(user.role)
                },
                refresh=True,
                expiry=timedelta(days=REFRESH_TOKEN_EXPIRY)
            )

        if isinstance(user_access_token, bytes):
            user_access_token = user_access_token.decode("utf-8")
        if isinstance(user_refresh_token, bytes):
            user_refresh_token = user_refresh_token.decode("utf-8")

            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "message": "Login succesfull",
                    "user_access_token": user_access_token,
                    "user_refresh_token": user_refresh_token,
                    "user_id": str(user.user_id),
                    "user_name": str(user.username),
                    'user_role': str(user.role)
                }
            )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Invalid Email  or Password"
    )


def verify_google_token(token: str):

    response = requests.get(
        f'https://oauth2.googleapis.com/tokeninfo?id_token={token}')

    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token")

    token_info = response.json()
    print(token_info['aud'])

    if token_info['aud'] != GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Token's audience doesn't match")
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
            raise HTTPException(
                status_code=404, detail="User not found, please register")
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
        raise HTTPException(
            status_code=401, detail="Could not validate credentials")
    except HTTPException as http_exc:
        raise http_exc
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



@auth_router.get("/user_profile/{userId}", response_model=list[dict])
async def user_profile(userId: UUID, session: AsyncSession = Depends(get_session), agent_details=Depends(access_token_bearer)):
    result = await session.execute(select(usertable).where(usertable.user_id == userId))
    user = result.scalars().first()

    if not user:
        return JSONResponse(status_code=404, content={"message": "User not found"})

    user_data = {
        "username": user.username,
        "email": user.email,
        "image": user.image,
        "gender": user.gender,
        "phone": user.phone,
        "date_of_birth": user.date_of_birth.isoformat() if user.date_of_birth else None,
        "marital_status": user.marital_status,
        "annual_income": user.annual_income,
        "city": user.city,
    }
    return JSONResponse(status_code=200, content={"user": user_data})


@auth_router.put("/profile_create/{userId}", response_model=dict)
async def update_profile(userId: UUID,
                         username: str = Form(...),
                         email: EmailStr = Form(...),
                         phone: str = Form(...),
                         gender: str = Form(...),
                         date_of_birth: str = Form(...),
                         city: str = Form(...),
                         marital_status: str = Form(...),
                         annual_income: str = Form(...),
                         image_url: Optional[str] = Form(None),
                         image: Optional[UploadFile] = File(None),
                         session: AsyncSession = Depends(get_session)):
    try:
        date_of_birth = datetime.strptime(date_of_birth, '%Y-%m-%d').date()
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Invalid date format, expected YYYY-MM-DD"
        )

    user_exists = await user_service.exist_user_id(userId, session)
    if not user_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="User not found"
        )

    user_data = ProfileCreateRequest(
        username=username,
        email=email,
        phone=phone,
        gender=gender,
        date_of_birth=date_of_birth,
        city=city,
        marital_status=marital_status,
        annual_income=annual_income
    )

    update_user = await user_service.profile_update(user_data, userId, image, session)

    return JSONResponse(status_code=200, content={"message": "Profile updated successfully"})


@auth_router.get("/listpolicy/{userId}", response_model=dict)
async def listpolicy(
    userId: UUID, 
    session: AsyncSession = Depends(get_session),
    user_details=Depends(access_token_bearer)
):

    result = await session.execute(select(usertable).where(usertable.user_id == userId))
    user = result.scalars().first()

    if user is None:
        return JSONResponse(status_code=404, content={"message": "User not found"})

    if not user.profile_status:
        return JSONResponse(status_code=400, content={"message": "Profile is not updated"})

    return JSONResponse(status_code=200,content={"message": "Profile is not updated"})
        



@auth_router.get("/policydetails/{userId}", response_model=dict)
async def user_policy_list(userId: UUID, session: AsyncSession = Depends(get_session),
                           user_details=Depends(access_token_bearer)):

    result = await session.execute(select(usertable).where(usertable.user_id == userId))
    user = result.scalars().first()

    if not user:
        return JSONResponse(status_code=404, content={"message": "Agent not found"})

    # Extract user details
    dob = user.date_of_birth
    income = user.annual_income

    print("User's Income:", income)

    # Calculate age
    today = date.today()
    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    print(f"User ID: {userId}, Age: {age}")

    # Fetch all policies
    policies_result = await session.execute(select(policytable).where(policytable.income_range == income))
    policies = policies_result.scalars().all()

    print("111111111")

    # Filter policies based on age group range
    matching_policies = []
    print("9999999999999999")
    print("qqqqqqqqqqqqqqqqqqq",policies)
    for policy in policies:
        try:
            min_age, max_age = map(int, policy.age_group.split('-'))  # Convert "26-35" to (26, 35)
            if min_age <= age <= max_age:
                # Policy Details
                print("22222222222")
                policy_id = str(policy.policy_uid)
                coverage = policy.coverage
                settlement = policy.settlement
                premium_amount = float(policy.premium_amount)  # Ensure numeric conversion

                # Calculate Monthly Payment
                r = 0.06  # 6% Annual Interest Rate
                n = 12  # Monthly payments
                t = int(coverage) - age  # Years until age 60

                if t > 0:  # Ensure valid term
                    monthly_payment = (premium_amount * (r / n)) / (1 - pow(1 + (r / n), -n * t))
                    print("3333333333333")
                else:
                    monthly_payment = premium_amount / 12  # Default to simple monthly payment

                matching_policies.append({
                    "policy_id": policy_id,
                    "coverage": coverage,
                    "settlement": settlement,
                    "premium_amount": premium_amount,
                    "monthly_payment": round(monthly_payment, 2),  # Rounded for better readability
                })
                print("44444444444")
        except ValueError:
            print("55555555555555555")
            print(f"Invalid age group format: {policy.age_group}")

    if not matching_policies:
        print("666666666666666666")
        return JSONResponse(status_code=404, content={"message": "No matching policies found"})
    print("777777777777777777")
    return JSONResponse(status_code=200, content={"matching_policies": matching_policies})



