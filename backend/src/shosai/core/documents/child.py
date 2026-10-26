"""The extraction child: one document's text, read in a process of its own under hard limits.

`python -I -m shosai.core.documents.child FORMAT LIMIT` reads the document's bytes from its
standard input and writes one JSON line: `{"text", "truncated"}` or `{"error": code}`. Before
any parser is imported the process caps its memory, CPU time, open files and writes, so a bomb,
a parser's endless loop or a crash ends this process alone; the parent knows only what it
printed and how it ended. It reads no setting and gets no secret: its environment is empty.
"""

import json
import resource
import sys
from typing import Final

MEMORY_BYTES: Final = 1024**3
CPU_SECONDS: Final = 20
OPEN_FILES: Final = 64
# Больше входа читать незачем: вложение Leo не больше 10 МиБ.
MAX_INPUT_BYTES: Final = 16 * 1024**2


def limited() -> None:
    """Cap the process before any parser loads."""
    resource.setrlimit(resource.RLIMIT_AS, (MEMORY_BYTES, MEMORY_BYTES))
    resource.setrlimit(resource.RLIMIT_CPU, (CPU_SECONDS, CPU_SECONDS))
    resource.setrlimit(resource.RLIMIT_NOFILE, (OPEN_FILES, OPEN_FILES))
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def answer(payload: dict[str, object]) -> int:
    """The one line the parent reads."""
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return 0


def main(argv: list[str]) -> int:
    """Read the document from standard input and print its text or why not."""
    limited()
    # Разборщики грузятся только после ограничений.
    from shosai.core.documents.formats import DocumentFormat  # noqa: PLC0415
    from shosai.core.documents.readers import READERS, UnreadableError, collected  # noqa: PLC0415

    document, limit = DocumentFormat(argv[1]), int(argv[2])
    data = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
    if len(data) > MAX_INPUT_BYTES:
        return answer({"error": "too_large"})
    try:
        text, truncated = collected(READERS[document](data), limit)
    except UnreadableError as error:
        return answer({"error": error.code})
    except MemoryError:
        return answer({"error": "too_large"})
    # Недоверенный файл: любой сбой разборщика — его ответ «битый файл», а не падение процесса.
    except Exception as error:  # noqa: BLE001
        sys.stderr.write(type(error).__name__ + "\n")
        return answer({"error": "malformed"})
    return answer({"text": text, "truncated": truncated})


if __name__ == "__main__":
    sys.exit(main(sys.argv))
