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

chat_service = ChatService() 


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

from fastapi.staticfiles import StaticFiles
from pathlib import Path



import os

UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")


os.makedirs(UPLOAD_DIR, exist_ok=True)

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

def serialize_message(message_data):
    def convert_uuid_and_datetime(obj):
        if isinstance(obj, UUID):
            return str(obj)  # Convert UUID to string
        elif isinstance(obj, datetime):
            return obj.isoformat()  # Convert datetime to ISO 8601 string
        raise TypeError(f"Type {type(obj)} not serializable")

    # Ensure all UUIDs and datetime objects in the data are converted to strings
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
        print(f"Client {user_id} disconnected")


# active_connections: Dict[str, WebSocket] = {}

@app.websocket("/ws/webrtc/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    """WebRTC Signaling WebSocket"""
    await connection_manager.connect(user_id, websocket)

    try:
        while True:
            data = await websocket.receive_json()
            print("22222222222222",data)
            target_id = data.get("target_id")
            print("11111111111111111111111",target_id)
            if target_id:
                await connection_manager.send_personal_message(target_id, data)
            
    except WebSocketDisconnect:
        connection_manager.disconnect(user_id, websocket)
    except Exception as e:
        print(f"Error: {e}")
        connection_manager.disconnect(user_id, websocket)