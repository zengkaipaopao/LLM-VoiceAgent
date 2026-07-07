import asyncio
import os
import sys

from sqlalchemy import func, select, update

# Add backend directory to sys.path so we can import app modules
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
sys.path.append(backend_dir)

from app.core.database import AsyncSessionLocal
from app.core.config import settings
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
                    name="多语言通用预约 (Multilingual Base Appointment)",
                    code="base_appointment",
                    description="根据客户当前使用的语言自动切换回复语言，处理新建、变更和取消预约。",
                    category="booking",
                    system_prompt=(
                        "あなたは企業の電話受付を担当する多言語AIアシスタントです。"
                        "相手の最初の意味のある発話から使用言語を判断し、同じ言語で応答してください。"
                        "会話の途中で相手が言語を切り替えた場合は、次の応答から同じ言語へ自然に切り替えてください。"
                        "言語を判断できない場合は日本語を使用してください。"
                        "相手が明示的に別の言語を希望した場合は、その希望を優先してください。"
                        "どの言語でも自然で簡潔かつ丁寧に話し、相手の話を遮らず、"
                        "一度に一つだけ質問してください。"
                        "新規予約、予約変更、予約取消、一般的な問い合わせに対応します。"
                        "予約に必要な氏名、会社名、希望日時、用件、場所、追加要望を確認してください。"
                        "氏名、日時、電話番号などの重要情報は、相手が使用している言語で復唱して確認してください。"
                        "変更・取消の場合は、氏名、電話番号、元の予約日など複数の情報で対象を確認し、"
                        "確認できない場合は推測で処理しないでください。"
                        "会話開始時は短く挨拶し、まず用件を伺ってください。"
                    ),
                    extraction_prompt=(
                        "以下の会話から予約情報をJSONで抽出してください。"
                        "不明な項目はnullにし、推測で補完しないでください。"
                        "operationはcreate、update、cancelのいずれかにしてください。\n"
                        "{conversation}"
                    ),
                    extraction_schema={
                        "type": "object",
                        "properties": {
                            "caller_name": {"type": ["string", "null"]},
                            "company": {"type": ["string", "null"]},
                            "appointment_time": {"type": ["string", "null"]},
                            "appointment_content": {"type": "string"},
                            "category": {"type": ["string", "null"]},
                            "amount": {"type": ["string", "null"]},
                            "address": {"type": ["string", "null"]},
                            "extra_request": {"type": ["string", "null"]},
                            "operation": {
                                "type": "string",
                                "enum": ["create", "update", "cancel"],
                            },
                            "summary": {"type": "string"},
                            "confidence": {
                                "type": "number",
                                "minimum": 0,
                                "maximum": 1,
                            },
                        },
                        "required": [
                            "appointment_content",
                            "operation",
                            "summary",
                            "confidence",
                        ],
                    },
                    response_format="text",
                    is_active=True,
                    is_twilio_incoming_default=True,
                    llm_provider="gemini",
                    llm_model=settings.default_live_model,
                    temperature=0.7,
                    max_tokens=2048,
                    voice_provider="gemini",
                    voice_id=settings.default_live_voice or "Aoede",
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
