"""The model requests of the native proxy: a live conversation, or screenshots with a question.

The conversation goes to the model under the proxy's English rules and a line that asks for the
conversation's own language, the person's answer language when it is unclear; the client's
messages follow as they were said, the newest within the budget. Screenshots go in one message
of the person's with their question — or, without one, the proxy's own task — under rules of
their own; several frames are read as one task.
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
    PROXY_RESPONSES,
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


def chat_request(ask: ChatAsk, language: str) -> ChatRequest | None:
    """The conversation for the model; None when nothing in it was said."""
    kept = kept_conversation(ask.messages)
    if not kept:
        return None
    return ChatRequest(
        messages=(
            said(Role.SYSTEM, PROXY_RESPONSES),
            said(Role.SYSTEM, language_line(PROXY_LANGUAGE, language)),
            *(said(ROLES[message.role], message.content) for message in kept),
        ),
        max_output_tokens=answer_tokens(ask.max_tokens),
        temperature=answer_temperature(ask.temperature),
    )


def vision_request(ask: VisionAsk, language: str) -> ChatRequest:
    """The screenshots and the question for the model."""
    rules = [language_line(PROXY_VISION, language)]
    if len(ask.frames) > 1:
        rules.append(VISION_FRAMES.format(count=len(ask.frames)))
    images: Sequence[ImagePart] = [ImagePart(frame, media_type(frame)) for frame in ask.frames]
    question = ask.prompt.strip() or VISION_TASK
    return ChatRequest(
        messages=(
            said(Role.SYSTEM, " ".join(rules)),
            ChatMessage(Role.USER, (TextPart(question), *images)),
        ),
        max_output_tokens=ANSWER_TOKENS,
    )
