from .schemas import *
from fastapi import APIRouter, status, Depends, Form
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
from src.agent_side.models import *
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from src.mail import mail_config
from .service import AdminService
from sqlalchemy import or_

logger = logging.getLogger(__name__)

admin_router = APIRouter()
access_token_bearer = AccessTokenBearer()
admin_service = AdminService()
REFRESH_TOKEN_EXPIRY = 2


@admin_router.post("/admin_login")
async def admin_login_page(login_data: Admin_login, session: AsyncSession = Depends(get_session)):
    username = login_data.username
    password = login_data.password

    if username == 'Admin' and password == 'Admin':
        admin_access_token = create_access_token(
            user_data={
                'admin_username': username,
                'admin_role': 'admin'
            }
        )

        admin_refresh_token = create_access_token(
            user_data={
                'admin_username': username,
                'admin_role': 'admin'
            },
            refresh=True,
            expiry=timedelta(days=REFRESH_TOKEN_EXPIRY)
        )

        if isinstance(admin_access_token, bytes):
            admin_access_token = admin_access_token.decode("utf-8")
        if isinstance(admin_refresh_token, bytes):
            admin_refresh_token = admin_refresh_token.decode("utf-8")

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "message": "Login successful",
                "admin_access_token": admin_access_token,
                "admin_refresh_token": admin_refresh_token,
                "admin_username": username,
                'admin_role': 'admin'
            }
        )

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Invalid Email or Password"
    )



@admin_router.get("/user_date", response_model=list[dict])
async def user_list(session: AsyncSession = Depends(get_session),
                    user_details=Depends(access_token_bearer)):

    result = await session.execute(select(usertable).where(
        and_(
            usertable.role == 'user',
            usertable.delete_status == False
        )
    ))
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

    try:
        policy_exists = await admin_service.exist_policy(policy_data.policy_name,session)
        if policy_exists:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="A policy with this name already exists. Please choose a different name."
            )

        new_policy = await admin_service.create_new_policy(policy_data,session)
        if not new_policy:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create the policy due to an internal server error."
            )

        return JSONResponse(
            status_code=201,
            content={"message": "Policy created successfully!"}
        )

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while creating the policy. Please try again later."
        )


@admin_router.get("/policy_list", response_model=List[dict])
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
    policy_list = []
    for row in policies:
        policy_list.append({
            "policy_name": row[0],
            "policy_type": row[1],
            "block_status": row[2],
            "role": row[3],
            "policy_uid": str(row[4]),
            "id_proof": row[5],
            "passbook": row[6],
            "photo": row[7],
            "pan_card": row[8],
            "income_proof": row[9],
            "nominee_address_proof": row[10],
            "coverage": row[11],
            "settlement": row[12],
            "premium_amount": row[13],
            "age_group": row[14],
            "description": row[15],
            "income_range": row[16],
            "policy_id": row[17],
        })

    return JSONResponse(
        status_code=200,
        content={"policy": policy_list}
    )


@admin_router.get("/policy_edit_list/{policyId}", response_model=List[dict])
async def policy_data(policyId: UUID, session: AsyncSession = Depends(get_session),
                      policy_details=Depends(access_token_bearer)):
    result = await session.execute(select(
        policytable.policy_id,
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
    ).where(policytable.policy_uid == policyId))
    policies = result.all()
    policy_list = []
    for row in policies:
        policy_list.append({
            "policy_id": row[0],
            "policy_name": row[1],
            "policy_type": row[2],
            "block_status": row[3],
            "role": row[4],
            "policy_uid": str(row[5]),
            "id_proof": row[6],
            "passbook": row[7],
            "photo": row[8],
            "pan_card": row[9],
            "income_proof": row[10],
            "nominee_address_proof": row[11],
            "coverage": row[12],
            "settlement": row[13],
            "premium_amount": row[14],
            "age_group": row[15],
            "description": row[16],
            "income_range": row[17],
        })

    return JSONResponse(
        status_code=200,
        content={"policy": policy_list}
    )


@admin_router.put("/policy_edit/{policyId}", response_model=dict)
async def edit_policy(policyId: UUID, policy_data: PolicyediteRequest, session: AsyncSession = Depends(get_session)):

    try:
        result = await session.execute(select(policytable).
                                       where(policytable.policy_uid == policyId))
        policys = result.scalars().first()

        if not policys:
            raise HTTPException(status_code=404, detail="Policy not found")

        policys.policy_id = policy_data.policy_id
        policys.policy_name = policy_data.policy_name
        policys.policy_type = policy_data.policy_type
        policys.id_proof = policy_data.id_proof
        policys.passbook = policy_data.passbook
        policys.photo = policy_data.photo
        policys.pan_card = policy_data.pan_card
        policys.income_proof = policy_data.income_proof
        policys.nominee_address_proof = policy_data.nominee_address_proof
        policys.coverage = policy_data.coverage
        policys.settlement = policy_data.settlement
        policys.premium_amount = policy_data.premium_amount
        policys.age_group = policy_data.age_group
        policys.income_range = policy_data.income_range
        policys.description = policy_data.description

        await session.commit()

        return JSONResponse(
            status_code=200,
            content={"message": "Policy updated successfully!"}
        )
    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=422, detail=e.errors())
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(
            status_code=500, detail="Internal server error")


@admin_router.post("/admin_refresh_token")
async def get_new_access_token(token_details: dict = Depends(RefreshTokenBearer())):
    expiry_timestamp = token_details["exp"]
    if datetime.fromtimestamp(expiry_timestamp) > datetime.now():
        new_access_token = create_access_token(
            user_data=token_details['user']
        )
        if isinstance(new_access_token, bytes):
            new_access_token = new_access_token.decode('utf-8')
        return JSONResponse(content={"admin_access_token": new_access_token})
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
        ).where(AgentTable.approval_status == "processing",)
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
async def agent_approval(agentId: UUID, session: AsyncSession = Depends(get_session),
                         user_details=Depends(access_token_bearer)):
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
async def agent_rejected(agentId: UUID, reason: str = Form(...),
                         session: AsyncSession = Depends(get_session),
                         agent_details=Depends(access_token_bearer)):
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


@admin_router.get("/agent_list", response_model=List[dict])
async def agent_approved_list(session: AsyncSession = Depends(get_session),
                              user_details=Depends(access_token_bearer)):

    result = await session.execute(select(
        AgentTable.agent_name,
        AgentTable.agent_email,
        AgentTable.agent_userid,
        AgentTable.agent_id,
        AgentTable.role,
        AgentTable.block_status,
        AgentTable.phone,
        AgentTable.gender,
        AgentTable.date_of_birth,
        AgentTable.agent_profile,
        AgentTable.agent_login_status,
        AgentTable.city
    ).where(and_(
        AgentTable.approval_status == 'approved',
        AgentTable.delete_status == False
    )))

    agents = result.all()
    if not agents:
        return JSONResponse(status_code=404, content={"message": "Agent not found"})

    agent_data = []
    for row in agents:
        if len(row) < 12:  # Updated the length check to 12
            print(f"Row length is less than expected: {row}")
            continue

        agent_data.append({
            "name": row[0],
            "email": row[1],
            "agentid": row[2],
            "agentuid": str(row[3]),
            "role": row[4],
            "block_status": row[5],
            "phone": row[6],
            "gender": row[7],
            "date_of_birth": row[8].isoformat(),
            "profile": row[9],
            "status": row[10],
            "city": row[11],
        })

    return JSONResponse(status_code=200, content={"agents": agent_data})


@admin_router.put("/user_block/{userId}", response_model=dict)
async def block_user(userId: UUID,
                     session: AsyncSession = Depends(get_session),
                     user_details=Depends(access_token_bearer)):
    result = await session.execute(select(usertable).where(usertable.user_id == userId))
    user = result.scalar()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.block_status = not user.block_status
    await session.commit()
    return JSONResponse(status_code=200, content={"message": "Updated."})


@admin_router.put("/agent_block/{userId}", response_model=dict)
async def block_user(userId: UUID,
                     session: AsyncSession = Depends(get_session),
                     user_details=Depends(access_token_bearer)):
    result = await session.execute(select(AgentTable).where(AgentTable.agent_id == userId))
    user = result.scalar()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.block_status = not user.block_status
    await session.commit()
    return JSONResponse(status_code=200, content={"message": "Updated."})


@admin_router.put("/Policy_block/{userId}", response_model=dict)
async def block_user(userId: UUID,
                     session: AsyncSession = Depends(get_session),
                     user_details=Depends(access_token_bearer)):
    result = await session.execute(select(policytable).where(policytable.policy_uid == userId))
    policy = result.scalar()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    policy.block_status = not policy.block_status
    await session.commit()
    return JSONResponse(status_code=200, content={"message": "Updated."})


@admin_router.put("/user_delete/{userId}", response_model=dict)
async def block_user(userId: UUID,
                     session: AsyncSession = Depends(get_session),
                     user_details=Depends(access_token_bearer)):
    result = await session.execute(select(usertable).where(usertable.user_id == userId))
    user = result.scalar()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.delete_status = True
    await session.commit()
    return JSONResponse(status_code=200, content={"message": "Updated."})


@admin_router.put("/policy_delete/{userId}", response_model=dict)
async def block_user(userId: UUID,
                     session: AsyncSession = Depends(get_session),
                     user_details=Depends(access_token_bearer)):
    result = await session.execute(select(policytable).where(policytable.policy_uid == userId))
    policy = result.scalar()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    policy.delete_status = True
    await session.commit()
    return JSONResponse(status_code=200, content={"message": "Updated."})


@admin_router.put("/agent_delete/{userId}", response_model=dict)
async def block_user(userId: UUID,
                     session: AsyncSession = Depends(get_session),
                     user_details=Depends(access_token_bearer)):
    result = await session.execute(select(AgentTable).where(AgentTable.agent_id == userId))
    policy = result.scalar()
    if not policy:
        raise HTTPException(status_code=404, detail="Agent not found")

    policy.delete_status = True
    await session.commit()
    return JSONResponse(status_code=200, content={"message": "Updated."})



@admin_router.get("/PolicyDetails_list", response_model=dict)
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
                PolicyDetails.payment_status,PolicyDetails.feedback,
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
        logger.error(f"An error occurred: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while fetching policies: {str(e)}"
        )
    

@admin_router.get("/PolicyApprovalAndRejection/{PolicyId}", response_model=list[dict])
async def PolicyApprovalAndRejection(PolicyId: UUID, 
                                     session: AsyncSession = Depends(get_session), 
                                     policy_details=Depends(access_token_bearer)):

    result = await session.execute(select(PolicyDetails).where(PolicyDetails.policydetails_uid == PolicyId))
    policy = result.scalars().first()

    if not policy:
        return JSONResponse(status_code=404, content={"message": "Policy not found"})

    policy_data = {
        "policydetails_uid": str(policy.policydetails_uid),
        "policy_holder": policy.policy_holder,
        "policy_name": policy.policy_name,
        "policy_type": policy.policy_type,
        "nominee_name": policy.nominee_name,
        "nominee_relationship": policy.nominee_relationship,
        "coverage": policy.coverage,
        "settlement": policy.settlement,
        "premium_amount": policy.premium_amount,
        "age": policy.age,
        "gender":policy.gender,
        "income_range": policy.income_range,
        "id_proof": policy.id_proof,
        "passbook": policy.passbook,
        "photo": policy.photo,
        "pan_card": policy.pan_card,
        "income_proof": policy.income_proof,
        "nominee_address_proof": policy.nominee_address_proof,
        "feedback": policy.feedback,

    }
    return JSONResponse(status_code=200, content={"policy": policy_data})


@admin_router.put("/policy_approved/{PolicyId}", response_model=dict)
async def agent_approval(PolicyId: UUID, session: AsyncSession = Depends(get_session),
                         user_details=Depends(access_token_bearer)):
    
    result = await session.execute(select(PolicyDetails).where(PolicyDetails.policydetails_uid == PolicyId))
    policy = result.scalars().first()

    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    policy.policy_status = ApprovalStatus.approved
    policy.payment_status = True

    user_id = policy.user_id
    user_result = await session.execute(select(usertable).where(usertable.user_id == user_id))
    user = user_result.scalars().first()

    user.policy_status = True

    await session.commit()
    return JSONResponse(status_code=200, content={"message": "Updated."})


@admin_router.put("/policy_rejected/{PolicyId}", response_model=dict)
async def agent_rejected(PolicyId: UUID, reason: str = Form(...),
                         session: AsyncSession = Depends(get_session),
                         user_details=Depends(access_token_bearer)):
    
    result = await session.execute(select(PolicyDetails).where(PolicyDetails.policydetails_uid == PolicyId))
    policy = result.scalars().first()

    if not reason or reason.strip() == "":
        raise HTTPException(
            status_code=400, detail="Please provide a reason for rejection.")

    if not policy:
        raise HTTPException(status_code=404, detail="Agent not found")

    policy.policy_status = ApprovalStatus.rejected
    policy.feedback = reason

    await session.commit()
    return JSONResponse(status_code=200, content={"message": "Updated."})


