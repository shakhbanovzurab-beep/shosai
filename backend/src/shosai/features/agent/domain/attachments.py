"""A question's attachments: what the question keeps of each, and how the model reads them
(agent step 12b; Leo §7.4).

The question names each claimed upload — its name, type, size and object key. The run notes
what became of each: a document's beginning and the reference of its whole text, an image, or
the code of a file that could not be read. Every turn reads the notes again, wrapped as the
person's own file (`file:own`), so a later question can still speak of an earlier attachment
(`application/attachment_notes.py` words them).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

from shosai.core.agent_tools.provenance import Provenance
from shosai.features.agent.domain.wrapper import Label

# Пределы вложений: файлов на вопрос, знаков текста на файл и на вопрос, начала в контексте.
MAX_ATTACHMENTS: Final = 5
FILE_CHARS: Final = 65_536
QUESTION_CHARS: Final = 262_144
DIGEST_CHARS: Final = 4_000
OWN_FILE: Final = Label.of(Provenance.FILE_OWN)


@dataclass(frozen=True, slots=True)
class Attached:
    """A claimed upload as the question names it."""

    upload_id: str
    name: str
    type: str
    size: int
    key: str

    def listed(self) -> dict[str, Any]:
        """What the history shows of it: never the object's key."""
        return {"id": self.upload_id, "name": self.name, "size": self.size, "type": self.type}


def attached_of(stored: Sequence[Mapping[str, Any]]) -> list[Attached]:
    """The question's attachments as its row keeps them."""
    return [
        Attached(
            upload_id=str(item["id"]), name=str(item["name"]), type=str(item.get("type", "")),
            size=int(item.get("size", 0)), key=str(item["key"]),
        )
        for item in stored
        if "key" in item
    ]  # fmt: skip


def noted(digest: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    """The notes a question's digest keeps of its attachments."""
    notes = (digest or {}).get("attachments", [])
    return [note for note in notes if isinstance(note, Mapping)] if isinstance(notes, list) else []
