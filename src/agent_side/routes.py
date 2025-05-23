from fastapi import APIRouter, Depends, status, UploadFile, File, HTTPException, Form, Request, FastAPI, Query
from fastapi.responses import JSONResponse
from sqlmodel.ext.asyncio.session import AsyncSession
from .schemas import *
from .service import *
from .models import AgentTable, ApprovalStatus
from src.db.database import get_session
import logging
from pydantic import BaseModel, EmailStr, Field
from .dependencies import *
from sqlmodel import select
import uuid
from datetime import datetime
from uuid import UUID
from src.utils import verify_password, create_access_token, decode_token, random_code
from datetime import timedelta
import logging
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from src.mail import mail_config
from src.admin_side.models import *
from src.user_side.models import *
from src.user_side.service import UserService
from typing import List
from src.utils import generate_passwd_hash
from src.messages.models import *
from src.messages.connetct_manager import connection_manager
# from src.db.redis import *

agent_router = APIRouter()
access_token_bearer = AccessTokenBearer()
agent_validation = Validation()
agent_service = AgentService()
user_service = UserService()


REFRESH_TOKEN_EXPIRY = 2


@agent_router.post("/agent_sign", response_model=AgentCreateResponse, status_code=status.HTTP_201_CREATED)
async def agent_signup(username: str = Form(...),
                       email: EmailStr = Form(...),
                       password: str = Form(...),
                       confirm_password: str = Form(...),
                       phone: str = Form(...),
                       gender: str = Form(...),
                       date_of_birth: str = Form(...),
                       city: str = Form(...),
                       id_proof: UploadFile = File(...),
                       session: AsyncSession = Depends(get_session)):
    try:
        date_of_birth = datetime.strptime(date_of_birth, '%Y-%m-%d').date()

        is_password = await agent_validation.validate_password(password, session)
        if not is_password:
            raise HTTPException(
                status_code=400, detail="Password must be at least 8 characters, contain 1 uppercase, 1 lowercase, 1 digit, and 1 special character.")

        is_phone = await agent_validation.validate_phone(phone, session)
        if not is_phone:
            raise HTTPException(
                status_code=400, detail="Invalid phone number: must be a 10-digit number starting with 6-9.")

        is_file = await agent_validation.validate_file_type(id_proof, session)
        if not is_file:
            raise HTTPException(
                status_code=400, detail="Invalid file type: only .jpg, .jpeg, or .png files are allowed.")

        is_gender = await agent_validation.validate_gender(gender, session)
        if not is_gender:
            raise HTTPException(
                status_code=400, detail="Invalid gender: must be one of 'Male', 'Female', or 'Other'.")

        is_dob = await agent_validation.validate_date_of_birth(date_of_birth, session)
        if not is_dob:
            raise HTTPException(
                status_code=400, detail="Invalid date of birth: user must be 18 years or older.")

        is_city = await agent_validation.validate_city(city, session)
        if not is_city:
            raise HTTPException(
                status_code=400, detail="Invalid city: only letters and spaces are allowed, and it must be at least 2 characters long.")

        agent_data = AgentCreateRequest(username=username, email=email, password=password,
                                        confirm_password=confirm_password, phone=phone, gender=gender,
                                        date_of_birth=date_of_birth, city=city)

        agent_exists_with_email = await agent_service.exist_email(email, session)

        if agent_exists_with_email:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="User with email already exists")

        if agent_data.password != agent_data.confirm_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Passwords do not match")

        new_agent = await agent_service.create_user(agent_data, id_proof, session)
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={"message": "Registration successful! Please log in."}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@agent_router.post("/agent_login")
async def login_agent(agent_login_data: AgentLoginModel, session: AsyncSession = Depends(get_session)) -> JSONResponse:
    agentid = agent_login_data.agentid
    password = agent_login_data.password
    latitude = agent_login_data.latitude
    longitude = agent_login_data.longitude

    user = await agent_service.get_agent_by_agentid(agentid, session)

    if not agentid or not isinstance(agentid, str) or len(agentid) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid agent ID: must be a non-empty string with at least 3 characters."
        )

    try:
        latitude = float(latitude)
        longitude = float(longitude)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Latitude and longitude must be valid numbers."
        )

    if user is not None and user.block_status != False:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Agent is Blocked"
        )

    if user is not None and user.approval_status == "approved":
        password_valid = verify_password(password, user.password)

        result = await session.execute(select(AgentTable).where(AgentTable.agent_userid == agentid))
        agent = result.scalars().first()

        if agent:
            agent.agent_login_status = True
            agent.latitude = latitude
            agent.longitude = longitude

            await session.commit()

        if password_valid:
            agent_access_token = create_access_token(
                user_data={
                    'agent_email': user.agent_email,
                    'agnet_id': str(user.agent_id),
                    'agent_name': str(user.agent_name),
                    'agent_userid': str(user.agent_userid),
                    'agent_role': str(user.role)
                }
            )

            agent_refresh_token = create_access_token(
                user_data={
                    'agent_email': user.agent_email,
                    'agnet_id': str(user.agent_id),
                    'agent_name': str(user.agent_name),
                    'agent_userid': str(user.agent_userid),
                    'agent_role': str(user.role)
                },
                refresh=True,
                expiry=timedelta(days=REFRESH_TOKEN_EXPIRY)
            )

            if isinstance(agent_access_token, bytes):
                agent_access_token = agent_access_token.decode("utf-8")
            if isinstance(agent_refresh_token, bytes):
                agent_refresh_token = agent_refresh_token.decode("utf-8")

            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "message": "Login successful",
                    "agent_access_token": agent_access_token,
                    "agent_refresh_token": agent_refresh_token,
                    'agent_email': user.agent_email,
                    'agnet_id': str(user.agent_id),
                    'agent_name': str(user.agent_name),
                    'agent_userid': str(user.agent_userid),
                    'agent_role': str(user.role)
                }
            )

    elif user is not None and user.approval_status != "approved":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Agent is not approved by admin"
        )

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Invalid agent ID or Password"
    )


@agent_router.put("/agent_logout/{agentId}")
async def logout_agent(
    agentId: UUID,
    session: AsyncSession = Depends(get_session),
    user_details=Depends(access_token_bearer),
):
    # jti = user_details['jti']
    # await add_jti_to_blocklist(jti)

    result = await session.execute(select(AgentTable).where(AgentTable.agent_id == agentId))
    agent = result.scalars().first()

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    agent.agent_login_status = False
    await connection_manager.disconnect_all(str(agentId))
    await session.commit()

    return JSONResponse(status_code=200, content={"message": "Agent logged out successfully."})


@agent_router.get("/agent_is_blocked/{agent_id}")
async def is_user_blocked(
    agent_id: UUID,
    session: AsyncSession = Depends(get_session),
    user_details=Depends(access_token_bearer),
):
    result = await session.execute(
        select(AgentTable.block_status).where(AgentTable.agent_id == agent_id)
    )
    block_status = result.scalar_one_or_none()

    if block_status is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    return JSONResponse(status_code=200, content={"block_status": block_status})


@agent_router.post("/agent_refresh_token")
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


@agent_router.get("/PolicyName", response_model=dict)
async def policyname(
    session: AsyncSession = Depends(get_session),
    user_details=Depends(access_token_bearer)
):
    try:

        result = await session.execute(select(policytable.policy_name))
        policies = result.scalars().all()

        filed_result = await session.execute(
            select(
                policytable.id_proof,
                policytable.passbook,
                policytable.income_proof,
                policytable.photo,
                policytable.pan_card,
                policytable.nominee_address_proof
            )
        )

        filed_data = filed_result.fetchall()
        field_keys = filed_result.keys()

        additional_fields = [dict(zip(field_keys, row)) for row in filed_data]

        return JSONResponse(
            status_code=200,
            content={
                "policies": policies,
                "additional_fields": additional_fields
            }
        )

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@agent_router.post("/ExistingCustomer/{agentID}")
async def ExistingCustomer(agentID: UUID,
                           email: EmailStr = Form(...),
                           insurancePlan: str = Form(...),
                           insuranceType: str = Form(...),
                           nomineeName: str = Form(...),
                           nomineeRelation: str = Form(...),
                           id_proof: Optional[UploadFile] = File(None),
                           passbook: Optional[UploadFile] = File(None),
                           income_proof: Optional[UploadFile] = File(None),
                           photo: Optional[UploadFile] = File(None),
                           pan_card: Optional[UploadFile] = File(None),
                           nominee_address_proof: Optional[UploadFile] = File(
                               None),
                           session: AsyncSession = Depends(get_session),
                           user_details=Depends(access_token_bearer)):


    is_insurancePlan = await agent_validation.validate_text(insurancePlan, session)
    if not is_insurancePlan:
        raise HTTPException(
            status_code=400, detail="Invalid insurancePlan: only letters and spaces are allowed.")

    is_insuranceType = await agent_validation.validate_text(insuranceType, session)
    if not is_insuranceType:
        raise HTTPException(
            status_code=400, detail="Invalid insuranceType: only letters and spaces are allowed.")

    is_nomineeName = await agent_validation.validate_text(nomineeName, session)
    if not is_nomineeName:
        raise HTTPException(
            status_code=400, detail="Invalid nomineeName: only letters and spaces are allowed.")

    is_nomineeRelation = await agent_validation.validate_text(nomineeRelation, session)
    if not is_nomineeRelation:
        raise HTTPException(
            status_code=400, detail="Invalid nomineeRelation: only letters and spaces are allowed.")

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
            is_valid = await agent_validation.validate_file_type(file, session)
            if not is_valid:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid file type for '{label}': only .jpg, .jpeg, or .png files are allowed."
                )

    result = await session.execute(select(usertable).where(usertable.email == email))
    user = result.scalars().first()
    if not user or not user.profile_status:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": "User profile is incomplete. Please update the profile before proceeding."})

    agent_data = ExistingUserPolicyRequest(
        email=email,
        policy_name=insurancePlan,
        policy_type=insuranceType,
        nominee_name=nomineeName,
        nominee_relationship=nomineeRelation,
    )
    try:
        update_user = await agent_service.ExistingUserPolicyCreation(
            agent_data, agentID, id_proof, passbook, income_proof,
            photo, pan_card, nominee_address_proof, session)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": f"An error occurred while updating the Policy: {str(e)}"}
        )

    if not update_user:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": "An error occurred while updating the Policy. Please try again later."}
        )

    return JSONResponse(status_code=200, content={"message": "Policy Submitted to admin"})


@agent_router.post("/NewCustomer/{agentID}")
async def new_customer(
    agentID: UUID,
    email: EmailStr = Form(...),
    name: str = Form(...),
    phone: str = Form(...),
    dob: str = Form(...),
    gender: str = Form(...),
    city: str = Form(...),
    maritalStatus: str = Form(...),
    income: str = Form(...),
    insurancePlan: str = Form(...),
    insuranceType: str = Form(...),
    nomineeName: str = Form(...),
    nomineeRelation: str = Form(...),
    id_proof: Optional[UploadFile] = File(None),
    passbook: Optional[UploadFile] = File(None),
    income_proof: Optional[UploadFile] = File(None),
    photo: Optional[UploadFile] = File(None),
    pan_card: Optional[UploadFile] = File(None),
    nominee_address_proof: Optional[UploadFile] = File(None),
    session: AsyncSession = Depends(get_session),
    user_details=Depends(access_token_bearer)
):
    try:

        date_of_birth = datetime.strptime(dob, '%Y-%m-%d').date()

        is_name = await agent_validation.validate_text(name, session)
        if not is_name:
            raise HTTPException(
                status_code=400, detail="Invalid name: only letters and spaces are allowed.")
        
        is_phone = await agent_validation.validate_phone(phone, session)
        if not is_phone:
            raise HTTPException(status_code=400, detail="Invalid phone number: must be a 10-digit number starting with 6-9.")

        is_marital_statu = await agent_validation.validate_marital_status(maritalStatus, session)
        if not is_marital_statu:
            raise HTTPException(status_code=400, detail="Invalid marital status: must be one of 'Single', 'Married', 'Divorced', or 'Widowed'.")

        is_gender = await agent_validation.validate_gender(gender, session)
        if not is_gender:
            raise HTTPException(status_code=400, detail="Invalid gender: must be one of 'Male', 'Female', or 'Other'.")

        is_dob = await agent_validation.validate_date_of_birth(date_of_birth, session)
        if not is_dob:
            raise HTTPException(status_code=400, detail="Invalid date of birth: user must be 18 years or older.")

        is_annual_income = await agent_validation.validate_annual_income(income, session)
        if not is_annual_income:
            raise HTTPException(status_code=400, detail="Invalid annual income: must be a positive number.")

        is_city = await agent_validation.validate_city(city, session)
        if not is_city:
            raise HTTPException(status_code=400, detail="Invalid city: only letters and spaces are allowed, and it must be at least 2 characters long.")


        is_insurancePlan = await agent_validation.validate_text(insurancePlan, session)
        if not is_insurancePlan:
            raise HTTPException(
                status_code=400, detail="Invalid insurancePlan: only letters and spaces are allowed.")

        is_insuranceType = await agent_validation.validate_text(insuranceType, session)
        if not is_insuranceType:
            raise HTTPException(
                status_code=400, detail="Invalid insuranceType: only letters and spaces are allowed.")

        is_nomineeName = await agent_validation.validate_text(nomineeName, session)
        if not is_nomineeName:
            raise HTTPException(
                status_code=400, detail="Invalid nomineeName: only letters and spaces are allowed.")

        is_nomineeRelation = await agent_validation.validate_text(nomineeRelation, session)
        if not is_nomineeRelation:
            raise HTTPException(
                status_code=400, detail="Invalid nomineeRelation: only letters and spaces are allowed.")

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
                is_valid = await agent_validation.validate_file_type(file, session)
                if not is_valid:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid file type for '{label}': only .jpg, .jpeg, or .png files are allowed."
                    )

        user_exists_with_email = await user_service.exist_email(email, session)
        if user_exists_with_email:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"message": "Email already used"}
            )
        new_user_data = NewUserPolicyRequest(
            username=name,
            email=email,
            phone=phone,
            date_of_birth=date_of_birth,
            gender=gender,
            city=city,
            marital_status=maritalStatus,
            annual_income=income,
            policy_name=insurancePlan,
            policy_type=insuranceType,
            nominee_name=nomineeName,
            nominee_relationship=nomineeRelation,
        )
        new_user = await agent_service.create_newuser(new_user_data, session)
        if not new_user:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"message": "User creation failed. Please try again later."}
            )

        agent_data = ExistingUserPolicyRequest(
            email=email,
            policy_name=insurancePlan,
            policy_type=insuranceType,
            nominee_name=nomineeName,
            nominee_relationship=nomineeRelation
        )
        update_user = await agent_service.ExistingUserPolicyCreation(
            agent_data, agentID, id_proof, passbook, income_proof, photo, pan_card, nominee_address_proof, session
        )
        if not update_user:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"message": "Policy creation failed. Please try again later."}
            )

        return JSONResponse(status_code=200, content={"message": "Policy Submitted to admin"})

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": f"An error occurred: {str(e)}"}
        )


@agent_router.get("/agent_profile/{agentID}", response_model=list[dict])
async def agent_profile(agentID: UUID, session: AsyncSession = Depends(get_session), agent_details=Depends(access_token_bearer)):
    result = await session.execute(select(AgentTable).where(AgentTable.agent_id == agentID))
    agent = result.scalars().first()

    if not agent:
        return JSONResponse(status_code=404, content={"message": "Agent not found"})

    agent_data = {
        "username": agent.agent_name,
        "email": agent.agent_email,
        "image": agent.agent_profile,
        "gender": agent.gender,
        "phone": agent.phone,
        "date_of_birth": agent.date_of_birth.isoformat() if agent.date_of_birth else None,
        "city": agent.city,
    }
    return JSONResponse(status_code=200, content={"agent": agent_data})


@agent_router.put("/AgentProfileUpdate/{agentID}", response_model=dict)
async def Agent_profile_update(agentID: UUID,
                               username: str = Form(...),
                               email: EmailStr = Form(...),
                               phone: str = Form(...),
                               gender: str = Form(...),
                               date_of_birth: str = Form(...),
                               city: str = Form(...),
                               image_url: Optional[str] = Form(None),
                               image: Optional[UploadFile] = File(None),
                               session: AsyncSession = Depends(get_session)):
    
    print("Received form data:")
    print(f"username={username}, email={email}, phone={phone}, gender={gender}, dob={date_of_birth}")
    print(f"city={city}, image={image.filename if image else 'None'}")
    try:
        date_of_birth = datetime.strptime(date_of_birth, '%Y-%m-%d').date()
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date format, expected YYYY-MM-DD"
        )
    
    is_username = await agent_validation.validate_text(username, session)
    if not is_username:
        raise HTTPException(status_code=400, detail="Invalid username: only letters and spaces are allowed.")
    
    is_phone = await agent_validation.validate_phone(phone, session)
    if not is_phone:
        raise HTTPException(status_code=500, detail="Invalid phone number: must be a 10-digit number starting with 6-9.")

    is_file = await agent_validation.validate_file_type(image, session)
    if not is_file:
        raise HTTPException(status_code=400, detail="Invalid file type: only .jpg, .jpeg, or .png files are allowed.")

    is_gender = await agent_validation.validate_gender(gender, session)
    if not is_gender:
        raise HTTPException(status_code=400, detail="Invalid gender: must be one of 'Male', 'Female', or 'Other'.")

    is_dob = await agent_validation.validate_date_of_birth(date_of_birth, session)
    if not is_dob:
        raise HTTPException(status_code=400, detail="Invalid date of birth: user must be 18 years or older.")

    is_city = await agent_validation.validate_city(city, session)
    if not is_city:
        raise HTTPException(status_code=400, detail="Invalid city: only letters and spaces are allowed, and it must be at least 2 characters long.")


    user_exists = await agent_service.exist_agent_id(agentID, session)
    if not user_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )

    agent_data = AgentProfileCreateRequest(
        username=username,
        email=email,
        phone=phone,
        gender=gender,
        date_of_birth=date_of_birth,
        city=city,
    )

    update_user = await agent_service.profile_update(agent_data, agentID, image, session)

    return JSONResponse(status_code=200, content={"message": "Profile updated successfully"})


@agent_router.get("/Policy_list/{PolicyId}", response_model=dict)
async def agent_policy_list(PolicyId: UUID, session: AsyncSession = Depends(get_session),
                            user_details=Depends(access_token_bearer)):
    try:
        result = await session.execute(
            select(
                PolicyDetails.policy_holder,
                PolicyDetails.policy_name,
                PolicyDetails.policy_type, PolicyDetails.nominee_name,
                PolicyDetails.nominee_relationship, PolicyDetails.premium_amount,
                PolicyDetails.coverage, PolicyDetails.date_of_birth,
                PolicyDetails.income_range, PolicyDetails.gender,
                PolicyDetails.feedback, PolicyDetails.id_proof,
                PolicyDetails.passbook, PolicyDetails.photo,
                PolicyDetails.pan_card, PolicyDetails.income_proof,
                PolicyDetails.nominee_address_proof, PolicyDetails.email, PolicyDetails.phone, PolicyDetails.marital_status,
                PolicyDetails.city,
            ).where(PolicyDetails.policydetails_uid == PolicyId)
        )

        policies = result.fetchone()
        if not policies:
            return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": "Policy not found"})

        policies_data = {
            "policy_holder": policies.policy_holder,
            "policy_name": policies.policy_name,
            "policy_type": policies.policy_type,
            "nominee_name": policies.nominee_name,
            "email": policies.email,
            "phone": policies.phone,
            "marital_status": policies.marital_status,
            "city": policies.city,
            "date_of_birth": policies.date_of_birth.isoformat() if policies.date_of_birth else None,
            "nominee_relationship": policies.nominee_relationship,
            "premium_amount": policies.premium_amount,
            "coverage": policies.coverage,
            "income_range": policies.income_range,
            "gender": policies.gender,
            "feedback": policies.feedback,
            "id_proof": policies.id_proof,
            "passbook": policies.passbook,
            "photo": policies.photo,
            "pan_card": policies.pan_card,
            "income_proof": policies.income_proof,
            "nominee_address_proof": policies.nominee_address_proof,
        }

        return JSONResponse(status_code=200, content={"policies": policies_data})

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while fetching policies: {str(e)}"
        )


@agent_router.put("/policyupdate/{PolicyId}")
async def policyupdates(
    PolicyId: UUID,
    email: EmailStr = Form(...),
    name: str = Form(...),
    phone: str = Form(...),
    dob: str = Form(...),
    gender: str = Form(...),
    city: str = Form(...),
    maritalStatus: str = Form(...),
    income: str = Form(...),
    insurancePlan: str = Form(...),
    insuranceType: str = Form(...),
    nomineeName: str = Form(...),
    nomineeRelation: str = Form(...),
    id_proof: Optional[UploadFile] = File(None),
    passbook: Optional[UploadFile] = File(None),
    income_proof: Optional[UploadFile] = File(None),
    photo: Optional[UploadFile] = File(None),
    pan_card: Optional[UploadFile] = File(None),
    nominee_address_proof: Optional[UploadFile] = File(None),
    session: AsyncSession = Depends(get_session),
    user_details=Depends(access_token_bearer)
):
    try:
        date_of_birth = datetime.strptime(dob, '%Y-%m-%d').date()


        if not PolicyId or not isinstance(PolicyId, str) or len(PolicyId) < 3:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Policy ID: must be a non-empty string with at least 3 characters."
            )
        
        is_name = await agent_validation.validate_text(name, session)
        if not is_name:
            raise HTTPException(
                status_code=400, detail="Invalid name: only letters and spaces are allowed.")
        
        is_phone = await agent_validation.validate_phone(phone, session)
        if not is_phone:
            raise HTTPException(status_code=400, detail="Invalid phone number: must be a 10-digit number starting with 6-9.")

        is_marital_statu = await agent_validation.validate_marital_status(maritalStatus, session)
        if not is_marital_statu:
            raise HTTPException(status_code=400, detail="Invalid marital status: must be one of 'Single', 'Married', 'Divorced', or 'Widowed'.")

        is_gender = await agent_validation.validate_gender(gender, session)
        if not is_gender:
            raise HTTPException(status_code=400, detail="Invalid gender: must be one of 'Male', 'Female', or 'Other'.")

        is_dob = await agent_validation.validate_date_of_birth(date_of_birth, session)
        if not is_dob:
            raise HTTPException(status_code=400, detail="Invalid date of birth: user must be 18 years or older.")

        is_annual_income = await agent_validation.validate_annual_income(income, session)
        if not is_annual_income:
            raise HTTPException(status_code=400, detail="Invalid annual income: must be a positive number.")

        is_city = await agent_validation.validate_city(city, session)
        if not is_city:
            raise HTTPException(status_code=400, detail="Invalid city: only letters and spaces are allowed, and it must be at least 2 characters long.")


        is_insurancePlan = await agent_validation.validate_text(insurancePlan, session)
        if not is_insurancePlan:
            raise HTTPException(
                status_code=400, detail="Invalid insurancePlan: only letters and spaces are allowed.")

        is_insuranceType = await agent_validation.validate_text(insuranceType, session)
        if not is_insuranceType:
            raise HTTPException(
                status_code=400, detail="Invalid insuranceType: only letters and spaces are allowed.")

        is_nomineeName = await agent_validation.validate_text(nomineeName, session)
        if not is_nomineeName:
            raise HTTPException(
                status_code=400, detail="Invalid nomineeName: only letters and spaces are allowed.")

        is_nomineeRelation = await agent_validation.validate_text(nomineeRelation, session)
        if not is_nomineeRelation:
            raise HTTPException(
                status_code=400, detail="Invalid nomineeRelation: only letters and spaces are allowed.")

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
                is_valid = await agent_validation.validate_file_type(file, session)
                if not is_valid:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid file type for '{label}': only .jpg, .jpeg, or .png files are allowed."
                    )

        user_exists_with_email = await user_service.exist_email(email, session)
        if not user_exists_with_email:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"message": "Email not found"}
            )

        new_user_data = NewUserPolicyRequest(
            username=name,
            email=email,
            phone=phone,
            date_of_birth=date_of_birth,
            gender=gender,
            city=city,
            marital_status=maritalStatus,
            annual_income=income,
            policy_name=insurancePlan,
            policy_type=insuranceType,
            nominee_name=nomineeName,
            nominee_relationship=nomineeRelation,
        )

        update_user = await agent_service.Policyupdate(
            new_user_data, PolicyId, id_proof, passbook, income_proof, photo, pan_card, nominee_address_proof, session
        )
        if not update_user:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"message": "Policy creation failed. Please try again later."}
            )

        return JSONResponse(status_code=200, content={"message": "Policy Submitted to admin"})

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": f"An error occurred: {str(e)}"}
        )


@agent_router.post('/password-recovery')
async def password_recovery(agent_id: AgentPasswordrecovery,
                            session: AsyncSession = Depends(get_session)):
    agentid = agent_id.agentID

    agent = await agent_service.exist_agent_user_id(agentid, session)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    result = await session.execute(select(AgentTable).where(AgentTable.agent_userid == agentid))
    agentinfo = result.scalars().first()
    await session.commit()

    reset_link = f"http://localhost:5173/AgentResetpassword"

    message = MessageSchema(
        subject="Password Reset Request",
        recipients=[agentinfo.agent_email],
        body=(
            f"Hello {agentinfo.agent_name},\n\n"
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
                                                  'agentID': str(agentid)})


@agent_router.post('/passwordreset')
async def password_reset(agent_data: RestpasswordModel, session: AsyncSession = Depends(get_session)):
    agent_id = agent_data.agentid
    password = agent_data.password

    is_password = await agent_validation.validate_password(password, session)
    if not is_password:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters, contain 1 uppercase, 1 lowercase, 1 digit, and 1 special character.")

    result = await session.execute(select(AgentTable).where(AgentTable.agent_userid == agent_id))
    agent = result.scalars().first()
    await session.commit()

    hashed_password = generate_passwd_hash(password)

    agent.password = hashed_password
    session.add(agent)

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


@agent_router.post("/customerdata", response_model=dict)
async def customerdata(
    customer_data: CutomerDataRequest,
    session: AsyncSession = Depends(get_session),
    agent_details=Depends(access_token_bearer)
):
    email = customer_data.email

    try:
        query = (
            select(
                PolicyDetails.policydetails_uid,
                PolicyDetails.policy_holder,
                PolicyDetails.policy_name,
                PolicyDetails.policy_type
            )
            .where(
                (PolicyDetails.email == email) &
                (PolicyDetails.policy_status == ApprovalStatus.approved) &
                (PolicyDetails.delete_status == False)
            )
        )

        result = await session.execute(query)
        policies = result.fetchall()

        if not policies:
            return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": "Customer not found"})

        customer_policies = [
            {
                "policydetails_uid": str(policy.policydetails_uid),
                "policy_holder": policy.policy_holder,
                "policy_name": policy.policy_name,
                "policy_type": policy.policy_type,
            }
            for policy in policies
        ]

        return JSONResponse(status_code=200, content={"policies": customer_policies})

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching policies."
        )


@agent_router.get("/customerinfo/{PolicyId}", response_model=dict)
async def customerinfo(
    PolicyId: UUID,
    session: AsyncSession = Depends(get_session),
    user_details=Depends(access_token_bearer)
):
    try:
        result = await session.execute(
            select(
                PolicyDetails.policydetails_uid,
                PolicyDetails.policy_holder,
                PolicyDetails.policy_name,
                PolicyDetails.policy_type,
                PolicyDetails.nominee_name,
                PolicyDetails.nominee_relationship,
                PolicyDetails.premium_amount,
                PolicyDetails.coverage,
                PolicyDetails.age,
                PolicyDetails.income_range,
                PolicyDetails.gender,
                PolicyDetails.photo,
                PolicyDetails.email,
                PolicyDetails.monthly_amount,
                PolicyDetails.phone,
                PolicyDetails.marital_status,
                PolicyDetails.city,
                PolicyDetails.payment_status,
            )
            .where(PolicyDetails.policydetails_uid == PolicyId))

        policies = result.mappings().first()

        if not policies:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"message": "Policy not found"},
            )

        policy_dict = {
            key: str(value) if isinstance(value, UUID) else value
            for key, value in dict(policies).items()
        }

        return JSONResponse(status_code=200, content={"policies": policy_dict})

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal server error occurred.",
        )


@agent_router.get("/search-suggestions", response_model=List[str])
async def search_suggestions(query: str, session: AsyncSession = Depends(get_session)):

    query = query.strip()

    if not query:
        raise HTTPException(
            status_code=400, detail="Query parameter is required.")

    stmt = select(PolicyDetails.email).where(
        PolicyDetails.email.ilike(f"%{query}%")).limit(5)

    result = await session.execute(stmt)
    emails = result.scalars().all()

    return emails if emails else []


@agent_router.get("/policy_list", response_model=List[dict])
async def policy_data(session: AsyncSession = Depends(get_session),
                      policy_details=Depends(access_token_bearer)):
    result = await session.execute(select(
        policytable.policy_name,
        policytable.policy_type,
        policytable.block_status,
        policytable.role,
        policytable.policy_uid,
        policytable.id_proof,
        policytable.passbook,
        policytable.photo,
        policytable.pan_card,
        policytable.income_proof,
        policytable.nominee_address_proof,
        policytable.coverage,
        policytable.settlement,
        policytable.premium_amount,
        policytable.age_group,
        policytable.description,
        policytable.income_range,
        policytable.policy_id,
    ).where(policytable.delete_status == False))
    policies = result.all()

    if not policies:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"message": "Policy not found"},
        )

    policy_list = []
    for row in policies:
        row_dict = {}
        for key, value in row._mapping.items():
            row_dict[key] = str(value) if isinstance(value, UUID) else value
        policy_list.append(row_dict)

    return JSONResponse(
        status_code=200,
        content={"policy": policy_list}
    )


@agent_router.get("/customercare/{agentId}", response_model=List[dict])
async def customercare(
    agentId: UUID,
    session: AsyncSession = Depends(get_session),
    policy_details=Depends(access_token_bearer),
):

    result = await session.execute(
        select(
            Message.uid,
            Message.content,
            Message.sender_id,
            Message.receiver_id
        ).where(Message.receiver_id == agentId)
    )
    customerdata = result.mappings().all()

    if not customerdata:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"message": "No messages found"},
        )

    sender_ids = {row["sender_id"] for row in customerdata}

    result = await session.execute(
        select(usertable.user_id, usertable.username)
        .where((usertable.delete_status == False) & (usertable.user_id.in_(sender_ids)))
    )
    users = {row["user_id"]: row["username"]
             for row in result.mappings().all()}

    unique_senders = {}
    for row in customerdata:
        sender_id = row["sender_id"]
        if sender_id not in unique_senders:
            unique_senders[sender_id] = {
                "uid": str(row["uid"]),
                "content": row["content"],
                "sender_id": str(sender_id),
                "receiver_id": str(row["receiver_id"]),
                "sender_name": users.get(sender_id, "Unknown"),
            }

    return JSONResponse(
        status_code=200,
        content={"messages": list(unique_senders.values())}
    )


@agent_router.get("/policiespermonth/{agentId}", response_model=dict)
async def policygraph(agentId: UUID, session: AsyncSession = Depends(get_session),
                      user_details=Depends(access_token_bearer)):

    try:
        result = await session.execute(
            select(
                PolicyDetails.policydetails_uid,
                PolicyDetails.create_at,
            ).where((PolicyDetails.policy_status == ApprovalStatus.approved) &
                    (PolicyDetails.agent_id == agentId) &
                    (PolicyDetails.delete_status == False))
        )

        policies = result.all()

        policies_data = [
            {
                "policydetails_uid": str(policy[0]),
                "create_at": policy[1].isoformat() if policy[1] else None,
            }
            for policy in policies
        ]
        return JSONResponse(status_code=200, content={"policies": policies_data})

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while fetching policies: {str(e)}"
        )


@agent_router.get("/policytakenbyagent", response_model=dict)
async def policytakenbyagent(session: AsyncSession = Depends(get_session),
                             user_details=Depends(access_token_bearer)):

    try:
        result = await session.execute(
            select(
                PolicyDetails.policydetails_uid,
                PolicyDetails.create_at,
            ).where((PolicyDetails.policy_status == ApprovalStatus.approved)
                    (PolicyDetails.delete_status == False) & (PolicyDetails.agent_id.isnot(None)))
        )

        policies = result.all()

        policies_data = [
            {
                "policydetails_uid": str(policy[0]),
                "create_at": policy[1].isoformat() if policy[1] else None,
            }
            for policy in policies
        ]

        return JSONResponse(status_code=200, content={"policies": policies_data})

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while fetching policies: {str(e)}"
        )


@agent_router.get("/policypaymentinfo/{agentId}", response_model=dict)
async def policypaymentinfo(agentId: UUID,
                            session: AsyncSession = Depends(get_session),
                            user_details=Depends(access_token_bearer)
                            ):
    try:
        result = await session.execute(
            select(
                PolicyDetails.policydetails_uid,
                PolicyDetails.policy_status,
                PolicyDetails.create_at
            ).where(PolicyDetails.delete_status.is_(False) & (PolicyDetails.agent_id == agentId))
        )

        policies = result.fetchall()

        if not policies:
            return JSONResponse(status_code=200, content={"message": "No policy data found", "policies": []})

        policies_data = [
            {
                "policydetails_uid": str(policy.policydetails_uid),
                "policy_status": policy.policy_status,
                "create_at": policy.create_at.isoformat() if policy.create_at else None,
            }
            for policy in policies
        ]

        return JSONResponse(status_code=200, content={"policies": policies_data})

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail="An internal server error occurred while fetching policy information."
        )


@agent_router.get("/PolicyDetails_list", response_model=dict)
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


@agent_router.post("/RazorpayPaymentCreation")
async def RazorpayPayment(payment: PaymentRequest, session: AsyncSession = Depends(get_session)):
    """Creates an order in Razorpay."""
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


@agent_router.post("/verify-payment/{PolicyId}")
async def verify_payment(
    PolicyId: UUID,
    request_data: PaymentVerificationRequest,
    session: AsyncSession = Depends(get_session)
):
    try:
        verification = await user_service.payment_verification(PolicyId, request_data, session)

        if verification:
            return {"status": "success", "message": "Payment verified"}

        raise HTTPException(
            status_code=400, detail="Invalid payment signature")

    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")
