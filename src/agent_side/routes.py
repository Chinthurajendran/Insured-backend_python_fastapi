from fastapi import APIRouter, Depends, status, UploadFile, File, HTTPException, Form, Request, FastAPI
from fastapi.responses import JSONResponse
from sqlmodel.ext.asyncio.session import AsyncSession
from .schemas import *
from .service import AgentService
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

agent_router = APIRouter()
access_token_bearer = AccessTokenBearer()
agent_service = AgentService()
REFRESH_TOKEN_EXPIRY = 2

logger = logging.getLogger(__name__)


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
    result = await session.execute(select(AgentTable).where(AgentTable.agent_id == agentId))
    agent = result.scalars().first()

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    agent.agent_login_status = False
    await session.commit()

    return JSONResponse(status_code=200, content={"message": "Agent logged out successfully."})


@agent_router.post("/refresh_token")
async def get_new_access_token(token_details: dict = Depends(RefreshTokenBearer())):
    expiry_timestamp = token_details["exp"]
    if datetime.fromtimestamp(expiry_timestamp) > datetime.now():
        new_access_token = create_access_token(
            user_data=token_details['user']
        )

        return JSONResponse(content={"access_token": new_access_token})
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid or expired token")


@agent_router.get("/PolicyName", response_model=dict)
async def policyname(
    session: AsyncSession = Depends(get_session),
    user_details=Depends(access_token_bearer)
):
    try:
        # Fetch policy names
        result = await session.execute(select(policytable.policy_name))
        policies = result.scalars().all()

        # Fetch additional fields
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

        filed_data = filed_result.fetchall()  # Get all rows
        field_keys = filed_result.keys()  # Get column names

        # Convert rows to a list of dictionaries
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
    
from typing import List

@agent_router.post("/ExistingCustomer")
async def ExistingCustomer(email: EmailStr = Form(...),
                           insurancePlan: str = Form(...),
                           insuranceType: str = Form(...),
                           nomineeName: str = Form(...),
                           nomineeRelation: str = Form(...), 
                           documents: List[UploadFile] = File(...),
                           session: AsyncSession = Depends(get_session),
                           user_details=Depends(access_token_bearer)):
    print("eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee")

    return JSONResponse(status_code=status.HTTP_200_OK)


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
    try:
        date_of_birth = datetime.strptime(date_of_birth, '%Y-%m-%d').date()
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Invalid date format, expected YYYY-MM-DD"
        )

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