from fastapi import FastAPI,WebSocket,Depends,WebSocketDisconnect
from contextlib import asynccontextmanager
from src.db.database import init_db
from src.user_side.routes import auth_router
from src.admin_side.routes import admin_router
from src.agent_side.routes import agent_router
from fastapi.middleware.cors import CORSMiddleware
from src.messages.connetct_manager import connection_manager
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.database import get_session,init_db
from src.messages.dependencies import AccessTokenBearer
from fastapi.exceptions import HTTPException
from src.messages.schemas import*
from src.messages.service import ChatService
import json
from datetime import datetime
from uuid import UUID
from src.messages.routes import messages_router
from src.user_side.models import Notification
from sqlmodel import select
from src.user_side.service import UserService
from src.user_side.routes import notification
from src.admin_side.models import PolicyDetails
import os
import asyncpg
DATABASE_URL =os.getenv("DATABASE_URL1")
import asyncio
from fastapi.staticfiles import StaticFiles
from pathlib import Path

chat_service = ChatService() 
user_service = UserService()


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Server is starting...")
    await init_db()
    yield
    print("Server is stopping...")

app = FastAPI(lifespan=lifespan)

app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
app.include_router(admin_router, prefix="/admin_auth", tags=["Admin Authentication"])
app.include_router(agent_router, prefix="/agent_auth", tags=["Agent Authentication"])
app.include_router(messages_router, prefix="/message_auth", tags=["Message Authentication"])


origins = [
    "http://localhost:5173"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")


os.makedirs(UPLOAD_DIR, exist_ok=True)

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

def serialize_message(message_data):
    def convert_uuid_and_datetime(obj):
        if isinstance(obj, UUID):
            return str(obj)
        elif isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Type {type(obj)} not serializable")

    return json.loads(json.dumps(message_data, default=convert_uuid_and_datetime))

@app.websocket("/ws/{user_id}")
async def chat_websocket_endpoint(
    websocket: WebSocket, 
    user_id: str, 
    session: AsyncSession = Depends(get_session)
):
    await connection_manager.connect(user_id, websocket)

    try:
        while True:
            data = await websocket.receive_json()
            message_data = MessageCreate(**data)
            saved_message = await chat_service.create_message(message_data,user_id,session)
            serialized_message = serialize_message(saved_message.dict())

            await connection_manager.broadcast(serialized_message)

    except WebSocketDisconnect:
        connection_manager.disconnect(user_id,websocket)


@app.websocket("/ws/webrtc/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    await connection_manager.connect(user_id, websocket)

    try:
        while True:
            data = await websocket.receive_json()
            target_id = data.get("target_id")
            if target_id:
                await connection_manager.send_personal_message(target_id, data)
            
    except WebSocketDisconnect:
        connection_manager.disconnect(user_id, websocket)
    except Exception as e:
        connection_manager.disconnect(user_id, websocket)

@app.websocket("/ws/webrtcvedio/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    await connection_manager.connect(user_id, websocket)

    try:
        while True:
            data = await websocket.receive_json()
            target_id = data.get("target_id")
            if target_id:
                await connection_manager.send_personal_message(target_id, data)
            
    except WebSocketDisconnect:
        connection_manager.disconnect(user_id, websocket)
    except Exception as e:
        connection_manager.disconnect(user_id, websocket)



async def listen_to_notifications(user_id, websocket: WebSocket):
    try:
        conn = await asyncpg.connect(DATABASE_URL)

        async def callback(connection, pid, channel, payload):
            notification = json.loads(payload)

            if str(notification["user_id"]) == str(user_id):
                await websocket.send_json(notification)

        await conn.add_listener("notification_channel", callback)

        while True:
            await asyncio.sleep(5) 

    except Exception as e:
        print(f"Error in listen_to_notifications: {e}")

    finally:
        await conn.remove_listener("notification_channel", callback)
        await conn.close()
        print("Database listener closed")


@app.websocket("/ws/notification/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: uuid.UUID):
    await websocket.accept()

    task = asyncio.create_task(listen_to_notifications(user_id, websocket))

    try:
        while True:
            message = await websocket.receive_text() 
    except WebSocketDisconnect:
        task.cancel()


@app.websocket("/ws/search/{agentId}")
async def chat_websocket_endpoint(
    websocket: WebSocket, 
    agentId: str, 
    session: AsyncSession = Depends(get_session)
):
    await connection_manager.connect(agentId, websocket)
  
    try:
        while True:
            data = await websocket.receive_json() 
            content = data.get("content", "").strip()
            if not content:
                await websocket.send_json({"error": "Query parameter is required."})
                continue 
            try:
                stmt = select(PolicyDetails.email).where(
                    PolicyDetails.email.ilike(f"%{content}%")
                ).limit(5)

                result = await session.execute(stmt)
                emails = result.scalars().all() 

                await websocket.send_json({"suggestions": emails})  

            except Exception as e:
                await websocket.send_json({"error": "Database query failed."})

    except WebSocketDisconnect:
        connection_manager.disconnect(agentId, websocket)
