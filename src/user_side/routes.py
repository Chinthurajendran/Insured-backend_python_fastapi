from fastapi import APIRouter, Depends, status, Form, UploadFile, File
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
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from src.mail import mail_config
from src.utils import generate_passwd_hash
from src.admin_side.models import *

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


@auth_router.post('/password-recovery')
async def password_recovery(user_email: Passwordrecovery,
                            session: AsyncSession = Depends(get_session)):

    email = user_email.email

    user = await user_service.exist_email(email, session)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    result = await session.execute(select(usertable).where(usertable.email == email))
    user = result.scalars().first()

    if user.block_status:
        raise HTTPException(status_code=403, detail="User is blocked")

    reset_link = f"http://localhost:5173/Resetpassword"

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
    except Exception as e:
        raise HTTPException(
            status_code=500, detail="Failed to send password reset email")

    return JSONResponse(status_code=200, content={"message": "Password recovery email sent successfully",
                                                  'email_id': str(email)})


@auth_router.post('/passwordreset')
async def password_reset(user_data: UserLoginModel, session: AsyncSession = Depends(get_session)):
    email = user_data.email
    password = user_data.password

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


@auth_router.post("/user_refresh_token")
async def get_new_access_token(token_details: dict = Depends(RefreshTokenBearer())):
    print("111111111111111")
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
            print(min_age)
            print(max_age)
            print(age)
            if min_age <= age <= max_age:
                policy_id = str(policy.policy_uid)
                coverage = policy.coverage
                settlement = policy.settlement
                premium_amount = float(policy.premium_amount)
                r = 0.06
                n = 12
                t = int(coverage) - age

                if t > 0:  # Ensure valid term
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
            print(f"Invalid age group format: {policy.age_group}")

    if not matching_policies:
        return JSONResponse(status_code=404, content={"message": "No matching policies found"})
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
            select(PolicyDetails.policy_status)
            .where(
                PolicyDetails.user_id == userId,
                PolicyDetails.policy_status.in_(["approved", "processing"])
            )
        )

        policies = result.scalars().all()

        if not policies:
            return JSONResponse(status_code=200, content={"policies": False})

        return JSONResponse(status_code=200, content={"policies": True})

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

        print("Raw Messages:", messages)
        serialized_messages = [
            {
                "notification_uid": str(row.notification_uid),
                "message": row.message,
                "create_at": row.create_at.isoformat()  
            }
            for row in messages
        ]

        print("Serialized Messages:", serialized_messages)

        return JSONResponse(status_code=200, content={"message": serialized_messages})

    except Exception as e:
        print(f"Error: {e}")
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
            msg.delete_status = True

        await session.flush()
        await session.commit()

        return JSONResponse(status_code=200, content={"message": "Deleted successfully"})

    except Exception as e:
        print(f"Error: {e}") 
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while deleting notifications: {str(e)}"
        )