"""Промпты, скиллы и модели «руководителя»; две модели реестра от администратора.

Промпты черновик показывает владельцу (администратору — только платформенные),
поэтому они у «руководителя». Плитки страницы промптов черновик считает по
расходам на модели (`provider_costs`) за 30 дней и с полуночи UTC; те же расходы
видит раздел администратора по всем пользователям.

Каталог моделей черновика — реестр: миграции переносят в него встроенные модели
без оценок. Две модели реестра засев добавляет с метриками — каталог покажет у
них оценки; одна из группы, недоступной тарифу Pro.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from meetassist.models.agent_skill import MODE_APPEND, MODE_REPLACE, AgentSkill, PromptSkill
from meetassist.models.model_registry import ModelRegistry
from meetassist.models.model_role_assignment import ModelRoleAssignment
from meetassist.models.prompt_template import PromptTemplate
from meetassist.models.provider_cost import ProviderCost
from meetassist.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession

from stable_ids import PROMPTS

_SALES_SYSTEM = (
    "Ты помогаешь на звонках с клиентом {{client}}. Отвечай коротко, опирайся на прошлые "
    "договорённости и не обещай скидок без согласования."
)

#: Промпты: ключ id, имя, роль, метки, версия, дней назад, активен, системный промпт.
_PROMPTS = (
    ("sales", "Ответы на звонках продаж", "responses", ["продажи", "эфир"], "v3", 1, True, _SALES_SYSTEM),
    (None, "Разбор скриншотов", "vision", ["скриншоты"], "v1", 3, True, "Опиши, что на скриншоте, и предложи ответ."),
    ("coding", "Собеседование: Python", "coding", ["собеседование", "python"], "v2", 5, True,
     "Помогай решать задачи на Python: сначала идея, потом код и сложность."),
    (None, "Тренер по System Design", "system_design", ["собеседование"], "v1", 8, True,
     "Веди разбор архитектуры: требования, оценка нагрузки, компоненты, компромиссы."),
    (None, "Заметки встречи", "generation", ["заметки"], "v1", 12, True, "Собери итоги встречи: решения, задачи, сроки."),
    (None, "Черновик ответов (старый)", "responses", ["черновик"], "v1", 20, False, "Отвечай развёрнуто."),
)

#: Скиллы: имя, репозиторий, путь, источник, установок, дней назад.
_SKILLS = (
    ("code-review", "acme/skills", "skills/code-review", "skills_sh", 1840, 6),
    ("star-method", "acme/skills", "skills/star-method", "skills_sh", 920, 9),
    ("sql-tuning", "parity/my-skills", "sql-tuning", "github", None, 15),
)

#: Модели расходов и их роли.
_SPEND_MODELS = (
    ("anthropic/claude-haiku-4.5", "responses"),
    ("qwen/qwen3-coder", "coding"),
    ("google/gemini-3-flash-preview", "vision"),
    ("deepseek/deepseek-v4-flash", "generation"),
)

_RUB_PER_USD = Decimal("95")


async def seed_prompts_models(db: AsyncSession, owner: User, admin: User, clock: datetime) -> None:
    """Засевает промпты, скиллы, расходы и назначения владельца и модели реестра."""
    prompts: dict[str, PromptTemplate] = {}
    for key, name, role, tags, version, days, active, system in _PROMPTS:
        prompt = PromptTemplate(name=name, role=role, tags=tags, version_tag=version, system_prompt=system,
                                user_prompt_template="Клиент: {{client}}\nВопрос: {{question}}" if key == "sales" else "",
                                variable_schema={"client": {"type": "string"}} if key == "sales" else None,
                                is_active=active, is_archived=False, user_id=owner.id,
                                created_at=clock - timedelta(days=days))
        if key is not None:
            prompt.id = PROMPTS[key]
            prompts[key] = prompt
        db.add(prompt)
    skills = [
        AgentSkill(user_id=owner.id, source=source, repo=repo, skill_path=path, ref="3f2c9a1e0b7d4c5a", slug=slug,
                   description=f"Чек-лист {slug}: шаги и критерии", body=f"# {slug}\n\n- Шаг 1\n- Шаг 2",
                   source_url=f"https://github.com/{repo}/tree/3f2c9a1e0b7d4c5a/{path}", installs=installs,
                   created_at=clock - timedelta(days=days))
        for slug, repo, path, source, installs, days in _SKILLS
    ]
    db.add_all(skills)
    await db.flush()
    db.add_all([
        PromptSkill(prompt_id=prompts["coding"].id, skill_id=skills[0].id, mode=MODE_APPEND, position=0),
        PromptSkill(prompt_id=prompts["coding"].id, skill_id=skills[1].id, mode=MODE_REPLACE, position=1),
    ])
    _spend(db, owner, clock)
    db.add(ModelRoleAssignment(user_id=owner.id, role="coding", model_id="deepseek/deepseek-v4-pro", model_type="chat",
                               temperature=0.2, max_tokens=8192, reasoning_enabled=None))
    db.add_all([
        _registry("mistralai/mistral-large-3", "Mistral • Large 3", "standard", "0.0005", "0.0015", admin, clock, 4),
        _registry("minimax/minimax-m2", "MiniMax • M2", "premium", "0.0003", "0.0012", admin, clock, 2),
    ])
    await db.flush()


def _spend(db: AsyncSession, owner: User, clock: datetime) -> None:
    """48 вызовов за месяц; шесть первых — сегодня, после полуночи UTC."""
    for index in range(48):
        model, role = _SPEND_MODELS[index % len(_SPEND_MODELS)]
        if index < 6:
            moment = clock - timedelta(minutes=5 * index + 1)
        else:
            moment = clock - timedelta(days=index % 29 + 1, hours=index % 7)
        usd = Decimal("0.0042") * (1 + index % 4)
        db.add(ProviderCost(user_id=owner.id, provider="openrouter", model_name=model, role=role,
                            input_tokens=1200 + 37 * index, output_tokens=300 + 11 * index,
                            latency_ms=600 + 45 * (index % 20), cost_usd=usd,
                            cost_rub=(usd * _RUB_PER_USD).quantize(Decimal("0.01")), exchange_rate_used=_RUB_PER_USD,
                            created_at=moment))


def _registry(model_id: str, display: str, tier: str, price_in: str, price_out: str, admin: User, clock: datetime,
              days: int) -> ModelRegistry:
    return ModelRegistry(
        openrouter_model_id=model_id, provider=model_id.split("/")[0], display=display, type="chat", tier=tier,
        capabilities=["CHAT", "STREAMING", "REASONING", "LONG CONTEXT"], context_window=262_144,
        pricing_input=Decimal(price_in), pricing_output=Decimal(price_out), enabled=True, version=1,
        created_by_user_id=admin.id, description="Strong long-context model for analysis and drafting.",
        description_source="Strong long-context model for analysis and drafting.",
        description_i18n={"en": "Strong long-context model for analysis and drafting.",
                          "ru": "Сильная модель с длинным контекстом для анализа и черновиков."},
        reasoning={"mandatory": False, "default_enabled": False},
        metrics={"intelligence": 48, "coding": 58, "agentic": 37, "throughput_tps": 110},
        created_at=clock - timedelta(days=days),
    )
