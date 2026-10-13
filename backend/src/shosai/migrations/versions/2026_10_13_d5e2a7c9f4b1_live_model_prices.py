"""Audio token units and the prices of live and transcription models (EU home, F6 step 3b).

Checked on 2026-10-13 against the providers' lists:

- OpenAI (`/api/docs/pricing`): gpt-live-transcribe and gpt-realtime-whisper $0.017 per
  minute of audio
- Google (`ai.google.dev/gemini-api/docs/pricing`), per million tokens: gemini-3.8-live
  text in $0.75, audio in $3.00, text out $4.50, audio out $12.00;
  gemini-3.5-live-translate-preview audio in $3.50, audio out $21.00
- OpenRouter (`/api/v1/models?output_modalities=transcription`): every transcription model
  not seeded before. Its `pricing.prompt` is per token when the model also has a
  `completion` price and per second of audio otherwise, which OpenAI's own list confirms
  (gpt-transcribe $0.0045 per minute is 0.000075 per second, OpenRouter's `prompt`).
  microsoft/mai-transcribe-2 and mai-transcribe-1.5 are left out: their `prompt` of 0.1
  and 0.36 fits neither unit, and the price sync of step 4 admits them once it is known.
"""

from decimal import Decimal

import sqlalchemy as sa
from alembic import op

from shosai.core.db.migration_scope import MigrationScope, runs_in
from shosai.core.kernel.homes import Home
from shosai.core.kernel.ids import new_id

revision: str = "d5e2a7c9f4b1"
down_revision: str | None = "c3d8f1a0b6e4"
branch_labels: str | None = None
depends_on: str | None = None
applies_to = (Home.EU,)

UNIT = "ck_provider_prices_unit_known"
UNITS = (
    "unit IN ('input_token', 'cached_input_token', 'output_token', 'input_audio_token', "
    "'output_audio_token', 'audio_second', 'page', 'document', 'request', 'image')"
)
FORMER_UNITS = (
    "unit IN ('input_token', 'cached_input_token', 'output_token', 'audio_second', 'page', "
    "'document', 'request', 'image')"
)
PER_SECOND_OF_MINUTE = Decimal("0.017") / 60
LIVE = (
    ("openai", "gpt-live-transcribe", "audio_second", PER_SECOND_OF_MINUTE),
    ("openai", "gpt-realtime-whisper", "audio_second", PER_SECOND_OF_MINUTE),
    ("google", "gemini-3.8-live", "input_token", Decimal("0.00000075")),
    ("google", "gemini-3.8-live", "input_audio_token", Decimal("0.000003")),
    ("google", "gemini-3.8-live", "output_token", Decimal("0.0000045")),
    ("google", "gemini-3.8-live", "output_audio_token", Decimal("0.000012")),
    ("google", "gemini-3.5-live-translate-preview", "input_audio_token", Decimal("0.0000035")),
    ("google", "gemini-3.5-live-translate-preview", "output_audio_token", Decimal("0.000021")),
)
TRANSCRIPTION = (
    ("assemblyai/universal-3-5-pro", "audio_second", "0.000125"),
    ("deepgram/nova-3", "audio_second", "0.0000716666666667"),
    ("elevenlabs/scribe-v2", "audio_second", "0.00003055555555555"),
    ("elevenlabs/scribe-v2-medical", "audio_second", "0.00003055555555555"),
    ("fish-audio/transcribe-1", "audio_second", "0.0001"),
    ("fish-audio/transcribe-1-pro", "audio_second", "0.0001"),
    ("google/chirp-3", "audio_second", "0.000266666666667"),
    ("google/gemini-3.5-transcribe", "input_token", "0.000002"),
    ("google/gemini-3.5-transcribe", "output_token", "0.000012"),
    ("meta/muse-voice-transcribe-1.0", "audio_second", "0.00005"),
    ("mistralai/voxtral-mini-3b-2507", "audio_second", "0.0000166667"),
    ("mistralai/voxtral-mini-transcribe", "audio_second", "0.00005"),
    ("mistralai/voxtral-small-24b-2507-stt", "audio_second", "0.00005"),
    ("nvidia/nemotron-3.5-asr-streaming-multilingual-0.6b", "audio_second", "0.00000333"),
    ("nvidia/parakeet-tdt-0.6b-v3", "audio_second", "0.000025"),
    ("openai/gpt-transcribe", "audio_second", "0.000075"),
    ("openai/whisper-large-v3", "audio_second", "0.0000075"),
    ("openai/whisper-large-v3-turbo", "audio_second", "0.00000333"),
    ("qwen/qwen3-asr-0.6b", "audio_second", "0.00000333"),
    ("qwen/qwen3-asr-1.7b", "audio_second", "0.0000075"),
    ("x-ai/grok-stt-1.0", "audio_second", "0.0000277777777778"),
)
SEEDS = LIVE + tuple(
    ("openrouter", model, unit, Decimal(price)) for model, unit, price in TRANSCRIPTION
)
PRICES = sa.table(
    "provider_prices",
    sa.column("id", sa.Uuid()),
    sa.column("provider", sa.Text()),
    sa.column("model", sa.Text()),
    sa.column("unit", sa.Text()),
    sa.column("price_usd", sa.Numeric(20, 12)),
    sa.column("effective_from", sa.DateTime(timezone=True)),
    sa.column("source", sa.Text()),
)


@runs_in(applies_to)
def upgrade(scope: MigrationScope) -> None:
    """Admit the audio token units, then append the seed prices, in force from now."""
    op.drop_constraint(op.f(UNIT), "provider_prices", type_="check")
    op.create_check_constraint(op.f(UNIT), "provider_prices", UNITS)
    op.execute(
        PRICES.insert().values(
            [
                {"id": new_id(), "provider": provider, "model": model, "unit": unit,
                 "price_usd": price.quantize(Decimal("1e-12")), "effective_from": sa.func.now(),
                 "source": "seed"}
                for provider, model, unit, price in SEEDS
            ]
        )
    )  # fmt: skip


@runs_in(applies_to)
def downgrade(scope: MigrationScope) -> None:
    """Remove the seed prices this revision appended and the audio token units."""
    for provider, model, unit, _ in SEEDS:
        op.execute(
            PRICES.delete().where(
                PRICES.c.provider == provider,
                PRICES.c.model == model,
                PRICES.c.unit == unit,
                PRICES.c.source == "seed",
            )
        )
    op.drop_constraint(op.f(UNIT), "provider_prices", type_="check")
    op.create_check_constraint(op.f(UNIT), "provider_prices", FORMER_UNITS)
