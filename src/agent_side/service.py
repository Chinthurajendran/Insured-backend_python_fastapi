from .models import AgentTable
from .schemas import *
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from datetime import datetime
from src.utils import generate_passwd_hash,UPLOAD_DIR,random_code
import logging
import aiofiles
from fastapi import UploadFile,File
from dotenv import load_dotenv
import os
import boto3
import traceback

load_dotenv()

logger = logging.getLogger(__name__)


BUCKET_NAME = os.getenv('S3_BUCKET_NAME')
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_REGION = os.getenv('AWS_REGION')

s3_client = boto3.client(
    's3',
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION
)

class AgentService:

    async def get_agent_by_id(self,agent_id:str,session:AsyncSession):
        statement = select(AgentTable).where(AgentTable.agent_id == agent_id)
        result = await session.exec(statement)

        user = result.first()
        
        return user

    async def get_agent_by_agentid(self, agentid: str, session: AsyncSession):
        statement = select(AgentTable).where(AgentTable.agent_userid == agentid)
        result = await session.exec(statement)
        agent = result.first()
        return agent
    
    async def exist_agent_id(self,agent_id:str,session:AsyncSession):
        user = await self.get_agent_by_id(agent_id,session)

        return True if user is not None else False
    

    async def exist_email(self, agentid: str, session: AsyncSession):
        agents = await self.get_agent_by_agentid(agentid, session)
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

        folder_name = "Agent/"

        file_path = f"{folder_name}{id_proof.filename}"

        s3_client.upload_fileobj(id_proof.file, BUCKET_NAME, file_path)
        file_url = f"https://{BUCKET_NAME}.s3.amazonaws.com/{file_path}"


        code = random_code()

        new_agent = AgentTable(
            agent_name=agent_data_dict["username"],
            agent_email=agent_data_dict["email"],
            phone=agent_data_dict["phone"],
            gender=agent_data_dict["gender"],
            date_of_birth=agent_data_dict["date_of_birth"],
            city=agent_data_dict["city"],
            agent_userid = f"AG{code}",
            password=generate_passwd_hash(agent_data_dict["password"]),
            agent_idproof= str (file_url),
            create_at=create_at,
            update_at=update_at
        )

        session.add(new_agent)
        await session.commit()
        await session.refresh(new_agent)

        logger.info(f"New user created: {new_agent.agent_name}")

        return new_agent


    async def profile_update(self, agent_data: AgentProfileCreateRequest, 
                             agentID, image: UploadFile, session: AsyncSession):
        try:
            if image is not None:
                folder_name = "Agent/Agnet Profile image/"

                file_path = f"{folder_name}{image.filename}"

                s3_client.upload_fileobj(image.file, BUCKET_NAME, file_path)
                file_url = f"https://{BUCKET_NAME}.s3.amazonaws.com/{file_path}"

            result = await session.execute(select(AgentTable).where(AgentTable.agent_id == agentID))
            agent = result.scalars().first()

            if not agent:
                return {"error": "Agent not found"}

            agent.agent_name = agent_data.username
            agent.agent_email = agent_data.email
            agent.phone = agent_data.phone
            agent.gender = agent_data.gender
            agent.date_of_birth = agent_data.date_of_birth
            agent.city = agent_data.city
            if image is not None:
                agent.agent_profile = file_url 

            session.add(agent)
            await session.flush()  # Ensure changes are detected
            await session.commit()  # Save changes to the database

            return {"message": "Profile updated successfully"}

        except Exception as e:
                await session.rollback()  # Rollback changes if an error occurs
                traceback.print_exc()  # Print the full error details
                return {"error": str(e)}



