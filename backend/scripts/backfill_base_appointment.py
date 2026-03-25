import asyncio
import os
import sys

from sqlalchemy import func, select, update

# Add backend directory to sys.path so we can import app modules
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
sys.path.append(backend_dir)

from app.core.database import AsyncSessionLocal
from app.models.appointment import Appointment
from app.services.prompt_service import PromptService


async def main():
    print("Starting data backfill for legacy appointments...")
    async with AsyncSessionLocal() as db:
        try:
            prompt_service = PromptService(db)

            # 1. Check if the base appointment prompt already exists
            template = await prompt_service.get_template("base_appointment")

            if not template:
                print("Creating 'base_appointment' prompt template...")
                template = await prompt_service.create_template(
                    name="通用预约 (Base Appointment)",
                    code="base_appointment",
                    description="Default schema for appointments created before dynamic schemas were introduced.",
                    category="booking",
                    system_prompt="You are an AI assistant specialized in booking general appointments.",
                    extraction_prompt="Extract caller name, company, appointment time, category, amount, address, and summary.",
                    response_format="json_object",
                    is_active=True,
                    llm_provider="gemini",
                    llm_model="gemini-2.0-flash",
                    temperature=0.7,
                    max_tokens=2048,
                )
                print(f"Created template with ID: {template.id}")
            else:
                print(f"Template already exists with ID: {template.id}")

            # 2. Update existing appointments that have NO prompt_id
            print("Migrating existing legacy appointments...")

            count_stmt = select(func.count(Appointment.id)).where(Appointment.prompt_id.is_(None))
            count = int(await db.scalar(count_stmt) or 0)
            print(f"Found {count} legacy appointments needing a prompt ID.")

            if count > 0:
                stmt = (
                    update(Appointment)
                    .where(Appointment.prompt_id.is_(None))
                    .values(
                        prompt_id=template.id,
                        type_name="base_appointment",
                        extracted_data={},
                    )
                )
                await db.execute(stmt)
                await db.commit()
                print(f"Successfully migrated {count} appointments to 'base_appointment'.")
            else:
                print("No legacy appointments needed migration.")

            print("Backfill completed successfully.")

        except Exception as e:
            print(f"An error occurred: {e}")
            await db.rollback()


if __name__ == "__main__":
    asyncio.run(main())
