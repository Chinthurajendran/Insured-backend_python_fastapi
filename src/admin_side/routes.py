from .schemas import *
from fastapi import APIRouter, status, Depends,Form
from sqlmodel.ext.asyncio.session import AsyncSession
from src.db.database import get_session
from fastapi.responses import JSONResponse
from src.utils import create_access_token
from datetime import timedelta
from .dependencies import *
from sqlmodel import select
from src.user_side.models import usertable
from typing import List
from .models import *
from fastapi import Request
from datetime import datetime
import uuid
from uuid import UUID
from src.user_side.models import usertable
from fastapi import HTTPException
from src.utils import verify_password
from sqlalchemy import and_
from pydantic import ValidationError
from fastapi import HTTPException
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError
import logging
from src.agent_side.models import*
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from src.mail import mail_config


logger = logging.getLogger(__name__)

admin_router = APIRouter()
access_token_bearer = AccessTokenBearer()
REFRESH_TOKEN_EXPIRY = 2


@admin_router.post("/admin_login")
async def admin_login_page(login_data: Admin_login, session: AsyncSession = Depends(get_session)):
    username = login_data.username
    password = login_data.password

    if username == 'Admin' and password == 'Admin':
        admin_access_token = create_access_token(
            user_data={
                'admin_username': username,
            }
        )

        admin_refresh_token = create_access_token(
            user_data={
                'admin_username': username,
            },
            refresh=True,
            expiry=timedelta(days=REFRESH_TOKEN_EXPIRY)
        )
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "message": "Login successful",
                "admin_access_token": admin_access_token,
                "admin_refresh_token": admin_refresh_token,
                "admin_username": username
            }
        )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Invalid Email or Password"
    )


@admin_router.get("/user_date", response_model=list[dict])
async def user_list(session: AsyncSession = Depends(get_session),
                    user_details=Depends(access_token_bearer)):

    result = await session.execute(select(usertable))
    users = result.scalars().all()

    users_dict = []
    for user in users:
        user_dict = user.__dict__.copy()
        user_dict.pop('_sa_instance_state', None)

        for key, value in user_dict.items():
            if isinstance(value, uuid.UUID):
                user_dict[key] = str(value)
            elif isinstance(value, datetime) or isinstance(value, date):
                user_dict[key] = value.isoformat()

        users_dict.append(user_dict)

    return JSONResponse(
        status_code=200,
        content={"users": users_dict}
    )


@admin_router.post("/policy_create", response_model=PolicyCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_policy(policy_data: PolicyCreateRequest, session: AsyncSession = Depends(get_session)):
    logger.info(f"Received request data: {policy_data}")

    try:
        result = await session.execute(select(policytable).where(policytable.policy_id == policy_data.policy_id))
        existing_policy = result.scalar()

        new_policy = policytable(
            policy_id=policy_data.policy_id,
            policy_name=policy_data.policy_name,
            policy_type=policy_data.policy_type,
            id_proof=policy_data.id_proof,
            passbook=policy_data.passbook,
            photo=policy_data.photo,
            pan_card=policy_data.pan_card,
            income_proof=policy_data.income_proof,
            nominee_address_proof=policy_data.nominee_address_proof,
            coverage=policy_data.coverage,
            settlement=policy_data.settlement,
            premium_amount=policy_data.premium_amount,
            age_group=policy_data.age_group,
            income_range=policy_data.income_range,
            description=policy_data.description,
            create_at=datetime.utcnow(),
            update_at=datetime.utcnow()
        )

        session.add(new_policy)
        await session.commit()
        await session.refresh(new_policy)

        return JSONResponse(
            status_code=201,
            content={"message": "Policy created successfully!"}
        )
    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=422, detail=e.errors())
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(
            status_code=500, detail="Policy with the given policy_id already exists.")


@admin_router.get("/policy_list", response_model=list[dict])
async def policy_data(session: AsyncSession = Depends(get_session),
                      policy_details=Depends(access_token_bearer)):

    result = await session.execute(select(policytable.policy_name, policytable.policy_type,
                                          policytable.id_proof, policytable.passbook, policytable.photo, policytable.pan_card,
                                          policytable.income_proof, policytable.nominee_address_proof, policytable.coverage,
                                          policytable.settlement, policytable.premium_amount, policytable.age_group,
                                          policytable.description, policytable.income_range,))
    policies = result.all()

    policy_list = [dict(zip(result.keys(), row)) for row in policies]
    return JSONResponse(
        status_code=200,
        content={"policy": policy_list}
    )


@admin_router.get("/refresh_token")
async def get_new_access_token(token_details: dict = Depends(RefreshTokenBearer())):
    expiry_timestamp = token_details["exp"]

    if datetime.fromtimestamp(expiry_timestamp) > datetime.now():
        new_access_token = create_access_token(
            user_data=token_details['user']
        )

        return JSONResponse(content={"access_token": new_access_token})
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid or expired token")




@admin_router.get("/agent_management", response_model=list[dict])
async def agent_management(
    session: AsyncSession = Depends(get_session),
    agent_details=Depends(access_token_bearer)
):
    result = await session.execute(
        select(
            AgentTable.agent_id, AgentTable.agent_name,
            AgentTable.agent_email, AgentTable.approval_status
        ).where(AgentTable.approval_status == "processing")
    )

    agents = result.all()

    agent_dict_list = []
    for agent in agents:
        agents_dict = dict(zip(result.keys(), agent))

        for key, value in agents_dict.items():
            if isinstance(value, uuid.UUID):
                agents_dict[key] = str(value)

        agent_dict_list.append(agents_dict)
    return JSONResponse(
        status_code=200,
        content={"agents": agent_dict_list}
    )


@admin_router.get("/agent_approval_and_rejection/{agentId}", response_model=list[dict])
async def agent_approval_and_rejection(agentId: UUID, session: AsyncSession = Depends(get_session), agent_details=Depends(access_token_bearer)):

    result = await session.execute(select(AgentTable).where(AgentTable.agent_id == agentId))
    agent = result.scalars().first()

    if not agent:
        return JSONResponse(status_code=404, content={"message": "Agent not found"})

    agent_data = {
        "agent_userid": agent.agent_userid,
        "name": agent.agent_name,
        "email": agent.agent_email,
        "phone": agent.phone,
        "gender": agent.gender,
        "date_of_birth": agent.date_of_birth.isoformat() if agent.date_of_birth else None,
        "idproof": agent.agent_idproof,
        "city": agent.city,
    }
    return JSONResponse(status_code=200, content={"agents": agent_data})


@admin_router.put("/agent_approved/{agentId}", response_model=dict)
async def agent_approval(agentId: UUID, session: AsyncSession = Depends(get_session), user_details=Depends(access_token_bearer)):
    logging.info(f"Attempting to approve agent with ID: {agentId}")
    logging.info(f"User details: {user_details}")

    result = await session.execute(select(AgentTable).where(AgentTable.agent_id == agentId))
    agent = result.scalars().first()

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    agent.approval_status = ApprovalStatus.approved


    logging.info(f"Using mail configuration: {mail_config}")

    message = MessageSchema(
        subject="Your Request Has Been Accepted",
        recipients=[agent.agent_email],
        body=f"Hello {agent.agent_name},\n\n"
        f"We are pleased to inform you that your request has been accepted by the admin.\n\n"
        f"To log in and check your status, please use the following agent ID: {agent.agent_userid}\n\n"
        f"Best regards,\n"
        f"Your Team",
        subtype="plain"
    )

    fm = FastMail(mail_config)
    try:
        await fm.send_message(message)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal Server Error")

    await session.commit()
    return JSONResponse(status_code=200, content={"message": "Updated."})



@admin_router.put("/agent_rejected/{agentId}", response_model=dict)
async def agent_rejected(agentId: UUID, reason: str = Form(...), session: AsyncSession = Depends(get_session), agent_details=Depends(access_token_bearer)):

    result = await session.execute(select(AgentTable).where(AgentTable.agent_id == agentId))
    agent = result.scalars().first()

    if not reason or reason.strip() == "":
        raise HTTPException(
            status_code=400, detail="Please provide a reason for rejection.")

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    agent.approval_status = ApprovalStatus.rejected
    agent.rejection_reason = reason

    message = MessageSchema(
            subject="Your Agent Registration Request Has Been Rejected",
            recipients=[agent.agent_email],
            body=f"Hello {agent.agent_name},\n\n"
                f"We regret to inform you that your request to register as an agent has been rejected.\n\n"
                f"Reason for rejection: {reason}\n\n"
                f"If you believe this was a mistake or need further clarification, please feel free to contact our support team.\n\n"
                f"Best regards,\n"
                f"Your Team",
            subtype="plain"
        )

    fm = FastMail(mail_config)
    try:
        await fm.send_message(message)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal Server Error")

    await session.commit()
    return JSONResponse(status_code=200, content={"message": "Updated."})




@admin_router.get("/agent_list", response_model=list[dict])
async def agent_approved_list(session: AsyncSession = Depends(get_session), user_details=Depends(access_token_bearer)):

    result = await session.execute(select(AgentTable.agent_name, AgentTable.agent_email,AgentTable.agent_userid,
                                          AgentTable.phone, AgentTable.gender,
                                          AgentTable.date_of_birth,
                                          AgentTable.agent_profile,
                                          AgentTable.agent_login_status, AgentTable.city).where(AgentTable.approval_status == 'approved'))
    agents = result.all()

    if not agents:
        return JSONResponse(status_code=404, content={"message": "Agent not found"})

    agent_data = []
    for row in agents:
        if len(row) < 9:
            print(f"Row length is less than expected: {row}")
            continue

        agent_data.append({
            "name": row[0],
            "email": row[1],
            "agentid": row[2],
            "phone": row[3],
            "gender": row[4],
            "date_of_birth": row[5].isoformat(),
            "profile": row[6],
            "status": row[7],
            "city": row[8],
        })

    return JSONResponse(status_code=200, content={"agents": agent_data})