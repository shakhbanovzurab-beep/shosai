"""The model requests of the native proxy: a live conversation, or screenshots with a question.

The conversation goes to the model under a frame that asks for the conversation's own language,
the person's answer language when it is unclear, then studio's layers (`proxy_studio.py`); the
client's messages follow as they were said, the newest within the budget. Screenshots go in one
message of the person's with their question — or, without one, the proxy's own task — under
rules of their own; several frames are read as one task. With studio's route the role's output
limit and temperature are the person's Studio settings; without it, the client's.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from shosai.core.ai.requests import ChatMessage, ChatRequest, ImagePart, Role, TextPart
from shosai.core.i18n.locales import LOCALE_BY_CODE
from shosai.features.agent.domain.proxy_input import (
    ANSWER_TOKENS,
    Said,
    answer_temperature,
    answer_tokens,
    kept_conversation,
    media_type,
)
from shosai.features.agent.infrastructure.prompts import (
    PROXY_LANGUAGE,
    PROXY_VISION,
    VISION_FRAMES,
    VISION_TASK,
)

ROLES: Final = {"system": Role.SYSTEM, "user": Role.USER, "assistant": Role.ASSISTANT}


@dataclass(frozen=True, slots=True)
class ChatAsk:
    """A client's conversation and its bounds."""

    messages: tuple[Said, ...]
    temperature: float | None = None
    max_tokens: int | None = None


@dataclass(frozen=True, slots=True)
class Tuning:
    """What studio's route asks of the call: the role's output limit and temperature."""

    max_tokens: int
    temperature: float | None


@dataclass(frozen=True, slots=True)
class VisionAsk:
    """A client's screenshots and its question, if any."""

    frames: tuple[bytes, ...]
    prompt: str = ""


def said(role: Role, text: str) -> ChatMessage:
    """A message of text only."""
    return ChatMessage(role, (TextPart(text),))


def language_line(template: str, language: str) -> str:
    """A rule naming the person's answer language by its tag and its own name."""
    locale = LOCALE_BY_CODE[language]
    return template.format(code=locale.code, name=locale.endonym)


def chat_frame(language: str) -> str:
    """The conversation's frame: the answer's language."""
    return language_line(PROXY_LANGUAGE, language)


def vision_frame(ask: VisionAsk, language: str) -> str:
    """The screenshots' frame: their rules, the language and how many frames are one task."""
    rules = [language_line(PROXY_VISION, language)]
    if len(ask.frames) > 1:
        rules.append(VISION_FRAMES.format(count=len(ask.frames)))
    return " ".join(rules)


def chat_request(
    ask: ChatAsk, system: Sequence[ChatMessage], tuning: Tuning | None
) -> ChatRequest | None:
    """The conversation for the model; None when nothing in it was said."""
    kept = kept_conversation(ask.messages)
    if not kept:
        return None
    limit = answer_tokens(ask.max_tokens)
    return ChatRequest(
        messages=(*system, *(said(ROLES[message.role], message.content) for message in kept)),
        max_output_tokens=limit if tuning is None else min(limit, tuning.max_tokens),
        temperature=answer_temperature(ask.temperature) if tuning is None else tuning.temperature,
    )


def vision_request(
    ask: VisionAsk, system: Sequence[ChatMessage], tuning: Tuning | None
) -> ChatRequest:
    """The screenshots and the question for the model."""
    images: Sequence[ImagePart] = [ImagePart(frame, media_type(frame)) for frame in ask.frames]
    question = ask.prompt.strip() or VISION_TASK
    return ChatRequest(
        messages=(*system, ChatMessage(Role.USER, (TextPart(question), *images))),
        max_output_tokens=ANSWER_TOKENS
        if tuning is None
        else min(ANSWER_TOKENS, tuning.max_tokens),
    )
