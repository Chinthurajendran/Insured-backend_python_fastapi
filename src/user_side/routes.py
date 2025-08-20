from fastapi import APIRouter, Depends, status, Form, UploadFile, File, Query, WebSocket, WebSocketDisconnect, FastAPI
from .schemas import *
from sqlmodel.ext.asyncio.session import AsyncSession
from src.db.database import get_session
from .service import *
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse
from src.utils import create_access_token, decode_token, verify_password
from datetime import timedelta,datetime
from .dependencies import *
from .models import *
from sqlmodel import select
from uuid import UUID
from .dependencies import *
from google.auth.transport import requests
from jose import JWTError
import requests
from typing import Optional
from typing import List
from src.admin_side.models import policytable
from math import pow
from fastapi_mail import FastMail, MessageSchema
from src.mail import mail_config
from src.utils import generate_passwd_hash
from src.admin_side.models import *
import pytz
from sqlalchemy.sql import func
from sqlalchemy import text
from src.agent_side.models import *
from src.messages.connetct_manager import connection_manager
from src.utils import random_code
import os
from sqlalchemy import and_
# from src.db.redis import*

auth_router = APIRouter()
user_service = UserService()
user_validation = Validation()
access_token_bearer = AccessTokenBearer()
REFRESH_TOKEN_EXPIRY = 2
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")


@auth_router.post("/emailvarfication", response_model=UserModel, status_code=status.HTTP_201_CREATED)
async def Emailvarfication(user_data: Emailvalidation, session: AsyncSession = Depends(get_session)):

    email = user_data.email.lower()
    user_exists_with_email = await user_service.exist_email(email, session)

    if user_exists_with_email:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Email already exists")
    
    code = random_code()

    message = MessageSchema(
        subject="Email Verification Code",
        recipients=[email],
        body=(
            f"Hello,\n\n"
            f"Thank you for registering with us!\n\n"
            f"To verify your email address, please use the following One-Time Password (OTP):\n\n"
            f"OTP: {code}\n\n"
            f"This code is valid for the next 2 minutes.\n\n"
            f"If you did not request this, please ignore this email.\n\n"
            f"Best regards,\n"
            f"Your Team"
        ),
        subtype="plain"
    )

    fm = FastMail(mail_config)
    try:
        await fm.send_message(message)
        ist = pytz.timezone("Asia/Kolkata")
        utc_time = datetime.utcnow().replace(tzinfo=pytz.utc)
        local_time = utc_time.astimezone(ist)
        local_time_naive = local_time.replace(tzinfo=None)

        OTP = OTPVerification(
            email = email,
            otp=str(code),
            created_at=local_time_naive,
            updated_at=local_time_naive
        )

        session.add(OTP)
        await session.commit()
        await session.refresh(OTP)
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={
                "message": "OTP has been successfully sent to your registered email address.",
            })
    
    except Exception as e:
        import logging
        logging.error(f"Error sending email or saving OTP: {e}")
        raise HTTPException(status_code=500, detail="Failed to send email")

@auth_router.post("/ResendOTP", status_code=status.HTTP_201_CREATED)
async def Resendotp(user_data: Emailvalidation, session: AsyncSession = Depends(get_session)):
    email = user_data.email.lower()
    
    result = await session.execute(select(OTPVerification).where(OTPVerification.email == email))
    existing_otp = result.scalars().first()

    if existing_otp is None:
        raise HTTPException(status_code=404, detail="Email not registered for verification.")

    code = random_code()

    message = MessageSchema(
        subject="Email Verification Code",
        recipients=[email],
        body=(
            f"Hello,\n\n"
            f"Thank you for registering with us!\n\n"
            f"To verify your email address, please use the following One-Time Password (OTP):\n\n"
            f"OTP: {code}\n\n"
            f"This code is valid for the next 2 minutes.\n\n"
            f"If you did not request this, please ignore this email.\n\n"
            f"Best regards,\n"
            f"Your Team"
        ),
        subtype="plain"
    )

    try:
        fm = FastMail(mail_config)
        await fm.send_message(message)

        ist = pytz.timezone("Asia/Kolkata")
        utc_time = datetime.utcnow().replace(tzinfo=pytz.utc)
        local_time = utc_time.astimezone(ist).replace(tzinfo=None)

        existing_otp.otp = str(code)
        existing_otp.created_at = local_time
        existing_otp.updated_at = local_time

        await session.commit()

        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={"message": "OTP has been successfully resent to your registered email address.",
                     "email": email}
        )

    except Exception as e:
        import logging
        logging.error(f"Error sending email or saving OTP: {e}")
        raise HTTPException(status_code=500, detail="Failed to send email")


@auth_router.post("/OTPverification", status_code=status.HTTP_201_CREATED)
async def OTPverifications(user_data: OTPverification, session: AsyncSession = Depends(get_session)):
    email = user_data.email.lower()
    OTP = user_data.OTP

    is_OTP = await user_validation.validate_otp(OTP, session)
    if not is_OTP:
        raise HTTPException(status_code=400, detail="Invalid OTP: must be a 6-digit number.")

    result = await session.execute(
        select(OTPVerification).where(
            and_(
                OTPVerification.email == email,
                OTPVerification.otp == OTP
            )
        )
    )

    existing_otp = result.scalars().first()

    if existing_otp is None:
        raise HTTPException(status_code=404, detail="Invalid email or OTP.")

    ist = pytz.timezone("Asia/Kolkata")
    utc_time = datetime.utcnow().replace(tzinfo=pytz.utc)
    now_ist = utc_time.astimezone(ist).replace(tzinfo=None)
    
    if now_ist - existing_otp.created_at > timedelta(minutes=1):
        raise HTTPException(status_code=400, detail="OTP has expired. Please request a new one.")
    
    return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "message": "OTP has been successfully verified.",
                "email": email
            }
        )


@auth_router.post("/signup", response_model=UserModel, status_code=status.HTTP_201_CREATED)
async def create_user_account(user_data: UserCreate, session: AsyncSession = Depends(get_session)):

    email = user_data.email.lower()
    username = user_data.username.lower()

    is_username = await user_validation.validate_text(username, session)
    if not is_username:
        raise HTTPException(status_code=400, detail="Invalid username: only letters and spaces are allowed.")
    
    is_password = await user_validation.validate_password(user_data.password, session)
    if not is_password:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters, contain 1 uppercase, 1 lowercase, 1 digit, and 1 special character.")

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


@auth_router.post('/password-recovery')
async def password_recovery(user_email: Passwordrecovery,
                            session: AsyncSession = Depends(get_session)):
    email = user_email.email
    user = await user_service.exist_email(email, session)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    result = await session.execute(
        select(usertable)
        .where(usertable.email == email))

    user = result.scalars().first()

    # reset_link = f"http://localhost:5173/Resetpassword"
    reset_link = f"http://insuredplus.shop/Resetpassword"

    message = MessageSchema(
        subject="Password Reset Request",
        recipients=[email],
        body=(
            f"Hello {user.username},\n\n"
            f"You requested a password reset. Click the link below to reset your password:\n\n"
            f"{reset_link}\n\n"
            f"If you didn't request this, please ignore this email.\n\n"
            f"Best regards,\nYour Support Team"
        ),
        subtype="plain"
    )

    fm = FastMail(mail_config)
    try:
        await fm.send_message(message)
        await session.commit()
    except Exception as e:
        raise HTTPException(
            status_code=500, detail="Failed to send password reset email")

    return JSONResponse(status_code=200, content={"message": "Password recovery email sent successfully",
                                                  'email_id': str(email)})


@auth_router.post('/passwordreset')
async def password_reset(user_data: UserLoginModel, session: AsyncSession = Depends(get_session)):
    email = user_data.email
    password = user_data.password

    is_password = await user_validation.validate_password(user_data.password, session)
    if not is_password:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters, contain 1 uppercase, " \
        "1 lowercase, 1 digit, and 1 special character.")

    result = await session.execute(select(usertable).where(usertable.email == email))
    user = result.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    hashed_password = generate_passwd_hash(password)

    user.password = hashed_password
    user_id = user.user_id
    message = "Password is reset"
    notification = await user_service.notification_update(user_id, message, session)

    if not notification:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Failed to create notification")

    session.add(user)

    try:
        await session.commit()
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to reset password")

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "message": "Password reset successful",
        }
    )


def verify_google_token(token: str):

    response = requests.get(
        f'https://oauth2.googleapis.com/tokeninfo?id_token={token}')

    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token")

    token_info = response.json()

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
        raise HTTPException(status_code=500, detail="Internal server error")


@auth_router.post("/user_refresh_token")
async def get_new_access_token(token_details: dict = Depends(RefreshTokenBearer())):
    expiry_timestamp = token_details["exp"]
    if datetime.fromtimestamp(expiry_timestamp) > datetime.now():
        new_access_token = create_access_token(
            user_data=token_details['user']
        )

        if isinstance(new_access_token, bytes):
            new_access_token = new_access_token.decode('utf-8')

        return JSONResponse(content={"access_token": new_access_token})
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid or expired token")


@auth_router.get("/user_is_blocked/{user_id}")
async def is_user_blocked(
    user_id: UUID,
    session: AsyncSession = Depends(get_session),
    user_details=Depends(access_token_bearer),
):
    result = await session.execute(
        select(usertable.block_status).where(usertable.user_id == user_id)
    )
    block_status = result.scalar_one_or_none()
    
    if block_status is None:
        raise HTTPException(status_code=404, detail="User not found")
    
    return JSONResponse(status_code=200, content={"block_status": block_status})


@auth_router.put("/user_logout/{user_id}")
async def logout_agent(
    user_id: UUID,
    session: AsyncSession = Depends(get_session),
    user_details : dict=Depends(access_token_bearer),
):
    # jti = user_details['jti']
    # await add_jti_to_blocklist(jti)

    result = await session.execute(select(usertable).where(usertable.user_id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await connection_manager.disconnect_all(str(user_id))

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
    
    print("Received form data:")
    print(f"username={username}, email={email}, phone={phone}, gender={gender}, dob={date_of_birth}")
    print(f"city={city}, marital_status={marital_status}, income={annual_income}, image={image.filename if image else 'None'}")

    try:
        date_of_birth = datetime.strptime(date_of_birth, '%Y-%m-%d').date()
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date format, expected YYYY-MM-DD"
        )
    
    is_username = await user_validation.validate_text(username, session)
    if not is_username:
        raise HTTPException(status_code=400, detail="Invalid username: only letters and spaces are allowed.")
    
    is_city = await user_validation.validate_city(city, session)
    if not is_city:
        raise HTTPException(status_code=400, detail="Invalid city: only letters and spaces are allowed, and it must be at least 2 characters long.")

    is_email = await user_validation.validate_email(email, session)
    if not is_email:
        raise HTTPException(status_code=400, detail="Invalid email format.")
    
    is_phone = await user_validation.validate_phone(phone, session)
    if not is_phone:
        raise HTTPException(status_code=400, detail="Invalid phone number: must be a 10-digit number starting with 6-9.")

    is_file = await user_validation.validate_file_type(image, session)
    if not is_file:
        raise HTTPException(status_code=400, detail="Invalid file type: only .jpg, .jpeg, or .png files are allowed.")

    is_marital_statu = await user_validation.validate_marital_status(marital_status, session)
    if not is_marital_statu:
        raise HTTPException(status_code=400, detail="Invalid marital status: must be one of 'Single', 'Married', 'Divorced', or 'Widowed'.")

    is_gender = await user_validation.validate_gender(gender, session)
    if not is_gender:
        raise HTTPException(status_code=400, detail="Invalid gender: must be one of 'Male', 'Female', or 'Other'.")

    is_dob = await user_validation.validate_date_of_birth(date_of_birth, session)
    if not is_dob:
        raise HTTPException(status_code=400, detail="Invalid date of birth: user must be 18 years or older.")

    is_annual_income = await user_validation.validate_annual_income(annual_income, session)
    if not is_annual_income:
        raise HTTPException(status_code=400, detail="Invalid annual income: must be a positive number.")


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

    return JSONResponse(status_code=200, content={"message": "Profile is not updated"})


@auth_router.get("/policydetails/{userId}", response_model=dict)
async def user_policy_list(userId: UUID, session: AsyncSession = Depends(get_session),
                           user_details=Depends(access_token_bearer)):
    result = await session.execute(select(usertable).where(usertable.user_id == userId))
    user = result.scalars().first()

    if not user:
        return JSONResponse(status_code=404, content={"message": "Agent not found"})

    dob = user.date_of_birth
    income = user.annual_income

    today = date.today()
    age = today.year - dob.year - \
        ((today.month, today.day) < (dob.month, dob.day))

    policies_result = await session.execute(select(policytable).where(policytable.income_range == income))
    policies = policies_result.scalars().all()

    matching_policies = []
    for policy in policies:
        try:
            min_age, max_age = map(int, policy.age_group.split('-'))
            if min_age <= age <= max_age:
                policy_id = str(policy.policy_uid)
                coverage = policy.coverage
                settlement = policy.settlement
                premium_amount = float(policy.premium_amount)
                r = 0.06
                n = 12
                t = int(coverage) - age

                if t > 0:
                    monthly_payment = (premium_amount * (r / n)) / \
                        (1 - pow(1 + (r / n), -n * t))
                else:
                    monthly_payment = premium_amount / 12

                matching_policies.append({
                    "policy_id": policy_id,
                    "coverage": coverage,
                    "settlement": settlement,
                    "premium_amount": premium_amount,
                    "monthly_payment": round(monthly_payment, 2),
                })
        except ValueError:
            return JSONResponse(status_code=200, content={"message": f"Invalid age group format: {policy.age_group}"})

    if not matching_policies:
        return JSONResponse(status_code=200, content={"message": "No matching policies found"})
    return JSONResponse(status_code=200, content={"matching_policies": matching_policies})


@auth_router.get("/policydocument/{policyId}", response_model=PolicyDetails)
async def user_policy_list(
    policyId: UUID,
    session: AsyncSession = Depends(get_session),
    user_details=Depends(access_token_bearer)
):
    policies_result = await session.execute(
        select(
            policytable.policy_name,
            policytable.policy_type,
            policytable.id_proof,
            policytable.passbook,
            policytable.photo,
            policytable.pan_card,
            policytable.income_proof,
            policytable.nominee_address_proof,
            policytable.coverage,
            policytable.settlement,
            policytable.premium_amount,
            policytable.income_range,
            policytable.description,
        ).where(policytable.policy_uid == policyId)
    )
    policies = policies_result.first()

    policy_dict = dict(policies._mapping)

    if policy_dict:
        return JSONResponse(
            status_code=200,
            content={
                "message": "Policy details retrieved successfully",
                "policy": policy_dict,
            },
        )
    else:
        raise HTTPException(status_code=404, detail="Policy not found")


@auth_router.post("/policyregistration/{policyId}/{userId}")
async def policy_registration(
    policyId: UUID,
    userId: UUID,
    nomineeName: str = Form(...),
    nomineeRelation: str = Form(...),
    id_proof: Optional[UploadFile] = File(None),
    passbook: Optional[UploadFile] = File(None),
    income_proof: Optional[UploadFile] = File(None),
    photo: Optional[UploadFile] = File(None),
    pan_card: Optional[UploadFile] = File(None),
    nominee_address_proof: Optional[UploadFile] = File(None),
    session: AsyncSession = Depends(get_session),
    user_details=Depends(access_token_bearer),
):
    is_nomineeName = await user_validation.validate_text(nomineeName, session)
    if not is_nomineeName:
        raise HTTPException(status_code=400, detail="Invalid nomineeName: only letters and spaces are allowed.")
    
    is_nomineeRelation = await user_validation.validate_text(nomineeRelation, session)
    if not is_nomineeRelation:
        raise HTTPException(status_code=400, detail="Invalid nomineeRelation: only letters and spaces are allowed.")
    
    files_to_validate = {
        "ID Proof": id_proof,
        "Passbook": passbook,
        "Income Proof": income_proof,
        "Photo": photo,
        "PAN Card": pan_card,
        "Nominee Address Proof": nominee_address_proof
    }
    for label, file in files_to_validate.items():
        if file is not None:
            is_valid = await user_validation.validate_file_type(file, session)
            if not is_valid:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid file type for '{label}': only .jpg, .jpeg, or .png files are allowed."
                )

    policy_register = PolicyRegistration(
        nominee_name=nomineeName,
        nominee_relationship=nomineeRelation,
    )

    update_user = await user_service.PolicyCreation(
        policy_register, policyId, userId, id_proof, passbook, income_proof, photo, pan_card, nominee_address_proof, session
    )

    if not update_user:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Policy creation failed. Please try again later.",
        )

    return JSONResponse(
        status_code=200,
        content={"message": "Policy details retrieved successfully"},
    )


@auth_router.get("/PolicyinfoDetails/{PolicyId}", response_model=list[dict])
async def policyinfo_details(PolicyId: UUID, session: AsyncSession = Depends(get_session)):

    try:
        result = await session.execute(
            select(
                policyinfo.policyinfo_name,
                policyinfo.photo,
                policyinfo.titledescription,
                policyinfo.description,
            ).where(policyinfo.policyinfo_uid == PolicyId)
        )

        policies = result.all()

        policies_data = [dict(zip(result.keys(), map(str, policy)))
                         for policy in policies]
        return JSONResponse(status_code=200, content={"policies": policies_data})

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while fetching policies: {str(e)}"
        )


@auth_router.get("/PolicyDetails_list", response_model=dict)
async def policy_list(session: AsyncSession = Depends(get_session),
                      user_details=Depends(access_token_bearer)):

    try:
        result = await session.execute(
            select(
                PolicyDetails.policydetails_uid, PolicyDetails.user_id,
                PolicyDetails.agent_id, PolicyDetails.policy_holder,
                PolicyDetails.policy_type, PolicyDetails.coverage,
                PolicyDetails.settlement, PolicyDetails.premium_amount,
                PolicyDetails.monthly_amount, PolicyDetails.age,
                PolicyDetails.income_range, PolicyDetails.policy_status,
                PolicyDetails.payment_status, PolicyDetails.feedback,
            )
        )

        policies = result.all()

        policies_data = [dict(policy._asdict()) for policy in policies]
        for policy in policies_data:
            policy['policydetails_uid'] = str(policy['policydetails_uid'])
            policy['user_id'] = str(policy['user_id'])
            policy['agent_id'] = str(policy['agent_id'])
            policy['policy_status'] = policy['policy_status'].value

        return JSONResponse(status_code=200, content={"policies": policies_data})

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while fetching policies: {str(e)}"
        )


@auth_router.get("/Policyinfo_list", response_model=list[dict])
async def policyinfo_list(session: AsyncSession = Depends(get_session)):

    try:
        result = await session.execute(
            select(
                policyinfo.policyinfo_uid,
                policyinfo.policyinfo_name,
                policyinfo.photo,
                policyinfo.titledescription,
                policyinfo.description,
                policyinfo.delete_status
            )
        )

        policies = result.all()

        policies_data = [dict(zip(result.keys(), map(str, policy)))
                         for policy in policies]

        return JSONResponse(status_code=200, content={"policies": policies_data})

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while fetching policies: {str(e)}"
        )


@auth_router.get("/UserPolicyStatus/{userId}")
async def Userpolicystatus(userId: UUID, session: AsyncSession = Depends(get_session)):
    try:
        result = await session.execute(
            select(PolicyDetails.policy_status, PolicyDetails.policy_id).where(
                PolicyDetails.user_id == userId,
                PolicyDetails.policy_status.in_(["approved", "processing"])
            )
        )
        policies = result.fetchall()

        if not policies:
            return JSONResponse(status_code=200, content={"policies": []})

        formatted_policies = [{"policy_id": str(
            policy.policy_id), "policy_status": policy.policy_status} for policy in policies]

        return JSONResponse(status_code=200, content={"policies": formatted_policies})

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while fetching policies: {str(e)}"
        )


@auth_router.get("/Getnotification/{userId}")
async def notification(userId: UUID, session: AsyncSession = Depends(get_session)):
    try:
        result = await session.execute(
            select(
                Notification.notification_uid,
                Notification.message,
                Notification.create_at
            ).where((Notification.user_id == userId) & (Notification.delete_status == False))
        )
        messages = result.fetchall()

        serialized_messages = [
            {
                "notification_uid": str(row.notification_uid),
                "message": row.message,
                "create_at": row.create_at.isoformat()
            }
            for row in messages
        ]
        if userId in connection_manager.active_connections:
            await connection_manager.send_personal_message(userId, {"event": "notificationsupdate"})

        return JSONResponse(status_code=200, content={"message": serialized_messages})

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while fetching notifications: {str(e)}"
        )


@auth_router.put("/Clearnotification/{userId}")
async def clearnotification(userId: UUID, session: AsyncSession = Depends(get_session)):
    try:
        result = await session.execute(
            select(Notification).where(Notification.user_id == userId)
        )
        messages = result.scalars().all()

        if not messages:
            return JSONResponse(status_code=404, content={"message": "No notifications found"})

        for msg in messages:
            await session.delete(msg)

        await session.flush()
        await session.commit()

        return JSONResponse(status_code=200, content={"message": "Deleted successfully"})

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while deleting notifications: {str(e)}"
        )


@auth_router.post("/RazorpayPaymentCreation")
async def RazorpayPayment(payment: PaymentRequest, session: AsyncSession = Depends(get_session)):
    try:

        if payment.amount <= 0:
            raise HTTPException(status_code=400, detail="Amount must be greater than 0")

        if not payment.currency.isalpha() or len(payment.currency) != 3:
            raise HTTPException(status_code=400, detail="Currency must be a 3-letter alphabetic code")

        if not payment.receipt.strip():
            raise HTTPException(status_code=400, detail="Receipt must not be empty")
        
        order_data = {
            "amount": payment.amount * 100,
            "currency": payment.currency,
            "receipt": payment.receipt,
            "payment_capture": 1
        }
        payment = await user_service.payment_creation(order_data, session)

        return payment
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@auth_router.post("/verify-payment/{PolicyId}")
async def verify_payment(
    PolicyId: UUID,
    request_data: PaymentVerificationRequest,
    session: AsyncSession = Depends(get_session)
):
    try:
        verification = await user_service.payment_verification(PolicyId, request_data, session)

        if verification:
            return {"status": "success", "message": "Payment verified"}
        await session.commit()

        raise HTTPException(
            status_code=400, detail="Invalid payment signature")

    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@auth_router.post("/PaymentUpdation")
async def PaymentUpdation(
    session: AsyncSession = Depends(get_session)
):
    try:
        ist = pytz.timezone("Asia/Kolkata")
        utc_time = datetime.utcnow().replace(tzinfo=pytz.utc)
        local_time = utc_time.astimezone(ist).replace(tzinfo=None)
        policy_data = await session.execute(
            select(PolicyDetails).where(
                PolicyDetails.payment_status == True,
                PolicyDetails.date_of_payment <= (
                    local_time - timedelta(days=30))
            )
        )

        policies = policy_data.scalars().all()

        if not policies:
            return {"message": "No policies require payment status update"}

        for policy in policies:
            policy.payment_status = False

        await session.commit()

        return {"message": f"{len(policies)} payment statuses updated successfully"}

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {str(e)}")


@auth_router.get("/WalletInfo/{userId}")
async def walletinfo(userId: UUID, session: AsyncSession = Depends(get_session)):
    try:
        result = await session.execute(
            select(
                Wallet.transaction_uid,
                Wallet.description,
                Wallet.amount,
                Wallet.transaction_type,
                Wallet.create_at
            ).where(Wallet.user_id == userId)
        )
        wallet = result.fetchall()

        wallet_data = [
            {
                "transaction_uid": str(row.transaction_uid),
                "description": row.description,
                "amount": row.amount,
                "transaction_type": row.transaction_type,
                "create_at": row.create_at.isoformat()
            }
            for row in wallet
        ]
        total_debit_result = await session.execute(
            select(func.sum(Wallet.amount)).where(
                (Wallet.user_id == userId) & (
                    Wallet.transaction_type == "Debit")
            )
        )
        total_debit = total_debit_result.scalar() or 0

        total_credit_result = await session.execute(
            select(func.sum(Wallet.amount)).where(
                (Wallet.user_id == userId) & (
                    Wallet.transaction_type == "Credit")
            )
        )
        total_credit = total_credit_result.scalar() or 0

        balance = total_debit - total_credit

        return JSONResponse(
            status_code=200,
            content={"wallet": wallet_data, "balance": balance}
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while fetching wallet data: {str(e)}"
        )


@auth_router.post("/wallet-verify-payment_add/{userId}")
async def wallet_verify_payment_add(
    userId: UUID,
    request_data: PaymentVerificationRequest,
    session: AsyncSession = Depends(get_session)
):
    try:

        verification = await user_service.wallet_payment_add(userId, request_data, session)

        if verification:
            return {"status": "success", "message": "Payment verified"}

        raise HTTPException(
            status_code=400, detail="Invalid payment signature")

    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@auth_router.post("/wallet-verify-payment-withdraw/{userId}")
async def wallet_verify_payment_withdraw(
    userId: UUID,
    request_data: PaymentVerificationRequest,
    type: str = Query(..., regex="^(wallet_policy|withdraw)$"),
    policy_id: Optional[UUID] = Query(None),
    session: AsyncSession = Depends(get_session)
):
    try:
        total_debit_result = await session.execute(
            select(func.sum(Wallet.amount)).where(
                (Wallet.user_id == userId) & (
                    Wallet.transaction_type == "Debit")
            )
        )
        total_debit = total_debit_result.scalar() or 0

        total_credit_result = await session.execute(
            select(func.sum(Wallet.amount)).where(
                (Wallet.user_id == userId) & (
                    Wallet.transaction_type == "Credit")
            )
        )
        total_credit = total_credit_result.scalar() or 0
        amount = int(request_data.amount) // 100

        balance = total_debit - total_credit-amount
        
        if balance <= 0:
            message = f"Transaction failed due to insufficient balance. You attempted to withdraw ₹{amount}, but your available balance is ₹{balance}."
            notification = await user_service.notification_update(userId, message, session)
            return JSONResponse(
                status_code=400,
                content={"error": "Insufficient balance", "balance": balance}
            )
        else:
            verification = await user_service.wallet_payment_withdraw(userId, request_data, type, session, policy_id)

            if verification:
                return {"status": "success", "message": "Payment verified"}

            raise HTTPException(
                status_code=400, detail="Invalid payment signature")

    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@auth_router.get("/nearestagent/{location}")
async def nearestagent(location: str, session: AsyncSession = Depends(get_session)):
    try:
        try:
            lat, lon = map(float, location.split(","))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid location format. Expected 'latitude,longitude'."
            )

        result = await session.execute(
            select(AgentTable.agent_id, AgentTable.latitude, AgentTable.longitude)
            .where((AgentTable.busy_status == False) & (AgentTable.agent_login_status == True))
            .order_by(func.abs(AgentTable.latitude - lat) + func.abs(AgentTable.longitude - lon))
            .limit(1)
        )
        nearest_agent = result.first()

        if not nearest_agent:
            result = await session.execute(
                select(AgentTable.agent_id, AgentTable.latitude,
                       AgentTable.longitude)
                .order_by(func.abs(AgentTable.latitude - lat) + func.abs(AgentTable.longitude - lon))
                .limit(1)
            )
            nearest_agent = result.first()
        if not nearest_agent:
            return JSONResponse(status_code=404, content={"message": "No agents available"})

        agent_id, agent_lat, agent_lon = nearest_agent
        return JSONResponse(status_code=200, content={"agents": [{"id": str(agent_id)}]})

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while fetching nearest agents: {str(e)}"
        )
