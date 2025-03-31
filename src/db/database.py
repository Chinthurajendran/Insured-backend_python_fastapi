from sqlmodel import create_engine,text,SQLModel
from sqlalchemy.ext.asyncio import AsyncEngine
from src.config import Config
from src.user_side.models import usertable
from src.admin_side.models import policytable
from src.agent_side.models import AgentTable
from src.messages.models import*
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import sessionmaker


engine = AsyncEngine(
    create_engine(
        url=Config.DATABASE_URL,
        echo=True
    )
)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        await conn.commit()

async def get_session() -> AsyncSession:
    Session = sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    # async with Session() as session:
    #     yield session
    
    async with Session() as session:
        try:
            yield session  # Provide session to route
            await session.commit()  # Explicitly commit before function exits
        except Exception:
            await session.rollback()  # Rollback only on failure
            raise
        finally:
            await session.close()  # Ensure session is closed properly
