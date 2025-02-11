


from fastapi import APIRouter, Depends, status, UploadFile, File, HTTPException,Form
from fastapi.responses import JSONResponse
from sqlmodel.ext.asyncio.session import AsyncSession
from .schemas import *
from .service import AgentService
from .models import AgentTable,ApprovalStatus
from src.db.database import get_session
import logging
from pydantic import BaseModel, EmailStr, Field
from .dependencies import AccessTokenBearer
from sqlmodel import select
import uuid
from datetime import datetime
from uuid import UUID
from src.utils import verify_password,create_access_token,decode_token
from datetime import timedelta
import logging

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
                                 confirm_password=confirm_password,phone=phone,gender=gender,
                                 date_of_birth=date_of_birth,city=city)
        logger.info(f"Received signup request for email: {email}")

        # Log received data
        logger.info(f"Received agent data: {agent_data.dict()}")
        logger.info(f"Received id_proof: {id_proof.filename if id_proof else 'No file uploaded'}")

        agent_exists_with_email = await agent_service.exist_email(email, session)
        if agent_exists_with_email:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User with email already exists")

        if agent_data.password != agent_data.confirm_password:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Passwords do not match")

        new_agent = await agent_service.create_user(agent_data, id_proof, session)
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={"message": "Registration successful! Please log in."}
        )
    except Exception as e:
        logger.error(f"Error during agent signup: {e}")
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    

# @agent_router.post("/agent_sign", response_model=AgentCreateResponse, status_code=status.HTTP_201_CREATED)
# async def agent_signup(agent_data: AgentCreateRequest = Depends(),
#                        id_proof: UploadFile = File(...),
#                        session: AsyncSession = Depends(get_session)):
#     try:
#         # date_of_birth = datetime.strptime(date_of_birth, '%Y-%m-%d').date()
#         # agent_data = AgentCreateRequest(username=username, email=email, password=password, 
#         #                          confirm_password=confirm_password,phone=phone,gender=gender,
#         #                          date_of_birth=date_of_birth,city=city)
#         # logger.info(f"Received signup request for email: {email}")

#         # Log received data
#         logger.info(f"Received agent data: {agent_data.dict()}")
#         logger.info(f"Received id_proof: {id_proof.filename if id_proof else 'No file uploaded'}")

#         agent_exists_with_email = await agent_service.exist_email(agent_data.email, session)
#         if agent_exists_with_email:
#             raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User with email already exists")

#         if agent_data.password != agent_data.confirm_password:
#             raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Passwords do not match")

#         new_agent = await agent_service.create_user(agent_data, id_proof, session)

#         return JSONResponse(
#             status_code=status.HTTP_201_CREATED,
#             content={"message": "Registration successful! Please log in."}
#         )
#     except Exception as e:
#         logger.error(f"Error during agent signup: {e}")
#         raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    
    

@agent_router.get("/agent_state", response_model=list[dict])
async def agent_aproval(
    session: AsyncSession = Depends(get_session),
    agent_details=Depends(access_token_bearer)
):
    result = await session.execute(
        select(
            AgentTable.agent_id, AgentTable.agent_name,
            AgentTable.agent_email, AgentTable.approval_status
        )
    )
    
    agents = result.all()  # Fetch all rows

    agent_dict_list = []
    for agent in agents:
        agents_dict = dict(zip(result.keys(), agent))  # Convert to dictionary
        
        # Convert UUID fields to strings
        for key, value in agents_dict.items():
            if isinstance(value, uuid.UUID):
                agents_dict[key] = str(value)
        
        agent_dict_list.append(agents_dict)
    return JSONResponse(
        status_code=200,
        content={"agents": agent_dict_list}
    )

@agent_router.get("/agent_approval/{agentId}", response_model=list[dict])
async def agent_approval_list(agentId: UUID, session: AsyncSession = Depends(get_session), user_details=Depends(access_token_bearer)):

    result = await session.execute(select(AgentTable).where(AgentTable.agent_id == agentId))
    agent = result.scalars().first()

    if not agent:
        return JSONResponse(status_code=404, content={"message": "Agent not found"})

    agent_data = {
        "name": agent.agent_name,
        "email": agent.agent_email,
        "phone": agent.phone,
        "gender": agent.gender,
        "date_of_birth": agent.date_of_birth.isoformat() if agent.date_of_birth else None,  # ✅ FIXED
        "idproof": agent.agent_idproof,
        # "idproof": agent.agent_idproof.split("\\")[-1],
        "city": agent.city,
    }

    return JSONResponse(status_code=200, content={"agents": agent_data})



@agent_router.put("/agent_rejected/{agentId}", response_model=dict)
async def agent_reject(agentId: UUID, session: AsyncSession = Depends(get_session), user_details=Depends(access_token_bearer)):
    logging.info(f"Attempting to reject agent with ID: {agentId}")
    logging.info(f"User details: {user_details}")

    result = await session.execute(select(AgentTable).where(AgentTable.agent_id == agentId))
    agent = result.scalars().first()

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    agent.approval_status = ApprovalStatus.rejected

    await session.commit()
    return JSONResponse(status_code=200, content={"message": "Updated."})



@agent_router.put("/agent_approved/{agentId}", response_model=dict)
async def agent_approve(agentId: UUID, session: AsyncSession = Depends(get_session), user_details=Depends(access_token_bearer)):
    logging.info(f"Attempting to reject agent with ID: {agentId}")
    logging.info(f"User details: {user_details}")

    result = await session.execute(select(AgentTable).where(AgentTable.agent_id == agentId))
    agent = result.scalars().first()

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    agent.approval_status = ApprovalStatus.approved

    await session.commit()
    return JSONResponse(status_code=200, content={"message": "Updated."})


@agent_router.get("/agent_list", response_model=list[dict])
async def agent_approval_list(session: AsyncSession = Depends(get_session), user_details=Depends(access_token_bearer)):

    result = await session.execute(select(AgentTable.agent_name, AgentTable.agent_email,
                                          AgentTable.phone, AgentTable.gender,
                                          AgentTable.date_of_birth,
                                          AgentTable.agent_profile,
                                          AgentTable.agent_login_status, AgentTable.city,))
    agents = result.all()

    if not agents:
        return JSONResponse(status_code=404, content={"message": "Agent not found"})

    agent_data = []
    for row in agents:
        if len(row) < 8:
            print(f"Row length is less than expected: {row}")
            continue  # Skip the row if it doesn't have the expected number of elements

        agent_data.append({
            "name": row[0],
            "email": row[1],
            "phone": row[2],
            "gender": row[3],
            "date_of_birth": row[4].isoformat(),
            "profile": row[5],
            "status": row[6],
            "city": row[7],
        })

    return JSONResponse(status_code=200, content={"agents": agent_data})

@agent_router.post("/agent_login")
async def login_agent(agent_login_data: AgentLoginModel, session: AsyncSession = Depends(get_session)) -> JSONResponse:
    email = agent_login_data.email
    password = agent_login_data.password

    user = await agent_service.get_agent_by_email(email, session)

    if user is not None and user.approval_status == "approved":
        password_valid = verify_password(password, user.password)

        if password_valid:
            access_token = create_access_token(
                user_data={
                    'email': user.agent_email,
                    'user_id': str(user.agent_id)
                }
            )

            refresh_token = create_access_token(
                user_data={
                    'email': user.agent_email,
                    'user_id': str(user.agent_id)
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
                    "user_id": str(user.agent_id),
                    "user_name": str(user.agent_email)
                }
            )

    elif user is not None and user.approval_status != "approved":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Agent is not approved by admin"
        )
        
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Invalid Email or Password"
    )

