from .schemas import *
from fastapi import APIRouter, status, Depends
from sqlmodel.ext.asyncio.session import AsyncSession
from src.db.database import get_session
from fastapi.responses import JSONResponse
from src.utils import create_access_token
from datetime import timedelta
from .dependencies import AccessTokenBearer
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

logger = logging.getLogger(__name__)

admin_router = APIRouter()
access_token_bearer = AccessTokenBearer()
REFRESH_TOKEN_EXPIRY = 2  

@admin_router.post("/admin_login")
async def admin_login_page(login_data: Admin_login, session: AsyncSession = Depends(get_session)):
    username = login_data.username
    password = login_data.password

    if username == 'Admin' and password == 'Admin':      
        access_token = create_access_token(
            user_data={
                'username': username,
            }
        )

        refresh_token = create_access_token(
            user_data={
                'username': username,
            },
            refresh=True,
            expiry=timedelta(days=REFRESH_TOKEN_EXPIRY)
        )
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "message": "Login successful",
                "access_token": access_token,
                "refresh_token": refresh_token,
                "user_name": username
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
        if existing_policy:
            raise HTTPException(status_code=400, detail="Policy with the given policy_id already exists.")
    
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
        raise HTTPException(status_code=500, detail="Internal Server Error")


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

