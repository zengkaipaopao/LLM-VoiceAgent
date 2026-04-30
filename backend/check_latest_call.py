import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

DATABASE_URL = "postgresql+asyncpg://dev_user:dev_password@localhost:5432/llm_voice_agent"
engine = create_async_engine(DATABASE_URL)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def main():
    async with async_session() as session:
        result = await session.execute(text("SELECT id, extra_data FROM calls ORDER BY created_at DESC LIMIT 1"))
        row = result.fetchone()
        if row:
            print("Latest Call ID:", row[0])
            print("Extra Data:", row[1])
        else:
            print("No calls found.")

if __name__ == "__main__":
    asyncio.run(main())
