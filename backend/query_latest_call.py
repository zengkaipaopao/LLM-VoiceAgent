import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
import json
from datetime import datetime

class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

async def main():
    db_url = "postgresql+asyncpg://dev_user:dev_password@localhost:5432/llm_voice_agent"
    engine = create_async_engine(db_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    try:
        async with async_session() as session:
            # Query recent calls
            query = text("SELECT * FROM calls ORDER BY created_at DESC LIMIT 1;")
            result = await session.execute(query)
            row = result.fetchone()
            
            if row:
                d = dict(row._mapping)
                print(json.dumps(d, cls=DateTimeEncoder, indent=2))
            else:
                print("No calls found in the database.")
    except Exception as e:
        print(f"Error querying database: {e}")
        
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
