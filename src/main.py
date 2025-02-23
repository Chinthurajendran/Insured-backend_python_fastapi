from fastapi import FastAPI
from contextlib import asynccontextmanager
from src.db.database import init_db
from src.user_side.routes import auth_router
from src.admin_side.routes import admin_router
from src.agent_side.routes import agent_router
from fastapi.middleware.cors import CORSMiddleware


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


origins = [
    "http://localhost:5173",
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




# app.mount("/uploads", StaticFiles(directory="D:/BROTOTYPE BOX/TASK/Week 23 1.0/Project 5.0/frontend/src/assets/uploads"), name="uploads")
import os

# Define a relative path for uploads
UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")

# Ensure the directory exists
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Mount the static folder
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

