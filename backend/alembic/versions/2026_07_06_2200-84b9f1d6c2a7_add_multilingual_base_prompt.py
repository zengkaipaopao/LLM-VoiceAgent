"""preserve Japanese base prompt and enable multilingual replies

Revision ID: 84b9f1d6c2a7
Revises: 5c8142e97a31
Create Date: 2026-07-06 22:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "84b9f1d6c2a7"
down_revision: Union[str, Sequence[str], None] = "5c8142e97a31"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


MULTILINGUAL_SYSTEM_PROMPT = (
    "あなたは企業の電話受付を担当する多言語AIアシスタントです。"
    "相手の最初の意味のある発話から使用言語を判断し、同じ言語で応答してください。"
    "会話の途中で相手が言語を切り替えた場合は、次の応答から同じ言語へ自然に切り替えてください。"
    "言語を判断できない場合は日本語を使用してください。"
    "相手が明示的に別の言語を希望した場合は、その希望を優先してください。"
    "どの言語でも自然で簡潔かつ丁寧に話し、相手の話を遮らず、一度に一つだけ質問してください。"
    "新規予約、予約変更、予約取消、一般的な問い合わせに対応します。"
    "予約に必要な氏名、会社名、希望日時、用件、場所、追加要望を確認してください。"
    "氏名、日時、電話番号などの重要情報は、相手が使用している言語で復唱して確認してください。"
    "変更・取消の場合は、氏名、電話番号、元の予約日など複数の情報で対象を確認し、"
    "確認できない場合は推測で処理しないでください。"
    "会話開始時は短く挨拶し、まず用件を伺ってください。"
)


def upgrade() -> None:
    # Preserve the original Japanese-only template as a selectable, non-routing
    # template. The live default keeps its ID so existing calls and appointments
    # continue to reference the same record.
    op.execute(
        sa.text(
            """
            INSERT INTO prompt_templates (
                name,
                code,
                description,
                category,
                system_prompt,
                extraction_prompt,
                variables,
                example_conversations,
                extraction_schema,
                response_format,
                output_schema,
                llm_provider,
                llm_model,
                temperature,
                max_tokens,
                voice_provider,
                voice_id,
                voice_settings,
                is_twilio_incoming_default,
                twilio_inbound_numbers,
                is_active,
                version,
                created_by,
                created_at,
                updated_at
            )
            SELECT
                '通用预约（日语原版）',
                'base_appointment_ja_legacy',
                '多语言切换改造前保留的日语电话接待模板。',
                category,
                system_prompt,
                extraction_prompt,
                variables,
                example_conversations,
                extraction_schema,
                response_format,
                output_schema,
                llm_provider,
                llm_model,
                temperature,
                max_tokens,
                voice_provider,
                voice_id,
                voice_settings,
                FALSE,
                NULL,
                is_active,
                version,
                created_by,
                NOW(),
                NOW()
            FROM prompt_templates
            WHERE code = 'base_appointment'
            ON CONFLICT (code) DO NOTHING
            """
        )
    )

    op.execute(
        sa.text(
            """
            UPDATE prompt_templates
            SET name = '多语言通用预约 (Multilingual Base Appointment)',
                description = '根据客户当前使用的语言自动切换回复语言，处理新建、变更和取消预约。',
                system_prompt = :system_prompt,
                version = COALESCE(version, 0) + 1,
                updated_at = NOW()
            WHERE code = 'base_appointment'
            """
        ).bindparams(system_prompt=MULTILINGUAL_SYSTEM_PROMPT)
    )


def downgrade() -> None:
    # Restore from the preserved copy without deleting it.
    op.execute(
        sa.text(
            """
            UPDATE prompt_templates AS target
            SET name = '通用预约 (Base Appointment)',
                description = source.description,
                system_prompt = source.system_prompt,
                version = source.version,
                updated_at = NOW()
            FROM prompt_templates AS source
            WHERE target.code = 'base_appointment'
              AND source.code = 'base_appointment_ja_legacy'
            """
        )
    )
