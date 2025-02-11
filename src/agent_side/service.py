from .models import AgentTable
from .schemas import *
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from datetime import datetime
from src.utils import generate_passwd_hash,UPLOAD_DIR


import logging
import aiofiles
from fastapi import UploadFile,File

logger = logging.getLogger(__name__)

class AgentService:
    async def get_agent_by_email(self, email: str, session: AsyncSession):
        statement = select(AgentTable).where(AgentTable.agent_email == email)
        result = await session.exec(statement)
        agent = result.first()
        return agent

    async def exist_email(self, email: str, session: AsyncSession):
        agents = await self.get_agent_by_email(email, session)
        return True if agents is not None else False

    async def create_user(
        self,
        agent_details: AgentCreateRequest,
        id_proof: UploadFile,
        session: AsyncSession
    ):
        agent_data_dict = agent_details.dict()
        create_at = datetime.utcnow()
        update_at = datetime.utcnow()

        file_path = UPLOAD_DIR / id_proof.filename
        async with aiofiles.open(file_path, "wb") as buffer:
            content = await id_proof.read()
            await buffer.write(content)

        new_agent = AgentTable(
            agent_name=agent_data_dict["username"],
            agent_email=agent_data_dict["email"],
            phone=agent_data_dict["phone"],
            gender=agent_data_dict["gender"],
            date_of_birth=agent_data_dict["date_of_birth"],
            city=agent_data_dict["city"],
            password=generate_passwd_hash(agent_data_dict["password"]),
            agent_idproof=str(file_path),
            create_at=create_at,
            update_at=update_at
        )

        session.add(new_agent)
        await session.commit()
        await session.refresh(new_agent)

        logger.info(f"New user created: {new_agent.agent_name}")

        return new_agent

















    # async def create_user(self,agent_details:AgentCreate,
    #                       id_proof:UploadFile = File(...),
    #                       session:AsyncSession):
    
    #     agent_data_dict = agent_details.model_dump()
    #     create_at = datetime.utcnow()
    #     update_at = datetime.utcnow()

    #     # Save uploaded file
    #     file_path = f"{UPLOAD_DIR}/{id_proof.filename}"
    #     with open(file_path, "wb") as buffer:
    #         shutil.copyfileobj(id_proof.file, buffer)

    #     new_agent = AgentTable(
    #         **agent_data_dict,
    #         id_proof=file_path,
    #         create_at=create_at,
    #         update_at=update_at
    #     )

    #     new_agent.password = generate_passwd_hash(agent_data_dict['password'])

    #     session.add(new_agent)
    #     await session.commit()
    #     await session.refresh(new_agent)

    #     logger.info(f"New user created: {new_agent.username}")

    #     return new_agent



