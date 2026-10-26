"""A question's attachments in Leo's turn: images beside the question, documents' text noted and
kept, a broken file failing alone, the notes read again on later turns (agent step 12b)."""

import json
import uuid

from shosai.core.ai.requests import ChatRequest, ImagePart, TextPart
from shosai.core.ai.results import ChatDelta
from shosai.features.agent.domain.attachments import DIGEST_CHARS
from tests.features.agent.tool_doubles import calling, saying
from tests.features.agent.turn_bench import HOME, TurnBench, stream_of
from tests.features.billing.people_bench import bearer
from tests.harness.connections import fetch_rows

PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 64


def question_of(request: ChatRequest) -> tuple[str, list[ImagePart]]:
    """The last message's text and images."""
    parts = request.messages[-1].parts
    text = "".join(part.text for part in parts if isinstance(part, TextPart))
    return text, [part for part in parts if isinstance(part, ImagePart)]


async def test_images_go_beside_the_question_and_documents_are_noted_and_kept(
    turn_bench: TurnBench,
) -> None:
    person = uuid.uuid4()
    thread = await turn_bench.thread(person)
    long_text = "Budget line. " * 1_000
    ids = [
        await turn_bench.attachment(person, "budget.txt", long_text.encode(), "text/plain"),
        await turn_bench.attachment(person, "chart.png", PNG, "image/png"),
        await turn_bench.attachment(person, "broken.pdf", b"%PDF-1.4 nothing", "application/pdf"),
    ]
    turn_bench.model.scripts = [saying("Read them.")]

    events = stream_of(await turn_bench.ask(person, thread, "What is in these?", upload_ids=ids))
    history = await turn_bench.http.get(
        f"/v1/agent/threads/{thread}/messages", headers=bearer((HOME, person))
    )

    text, images = question_of(turn_bench.model.calls[0])
    assert 'The person attached the file "budget.txt". Its text:' in text
    assert 'The person attached the image "chart.png" to this message.' in text
    assert 'attached the file "broken.pdf", but it could not be read (malformed)' in text
    assert "call core__read_result" in text
    assert [(image.media_type, len(image.data)) for image in images] == [("image/png", len(PNG))]
    steps = [
        (kind, data.get("activity"), data.get("detail"))
        for kind, _, data in events
        if kind == "step.started"
    ]
    assert steps[:3] == [
        ("step.started", "read_attachment", "budget.txt"),
        ("step.started", "read_attachment", "chart.png"),
        ("step.started", "read_attachment", "broken.pdf"),
    ]
    failed = [data.get("code") for kind, _, data in events if kind == "step.failed"]
    assert failed == ["malformed"]
    kept = await fetch_rows(
        turn_bench.connection,
        "SELECT payload FROM agent_tool_results WHERE tool_name = 'core.attachment'",
    )
    assert any(row["payload"]["json"] == long_text[: len(row["payload"]["json"])] for row in kept)
    [question] = [item for item in history.json()["items"] if item["role"] == "user"]
    assert [a["name"] for a in question["attachments"]] == ["budget.txt", "chart.png", "broken.pdf"]
    assert set(question["attachments"][0]) == {"id", "name", "size", "type"}


async def test_a_later_turn_reads_the_notes_again_without_the_images(turn_bench: TurnBench) -> None:
    person = uuid.uuid4()
    thread = await turn_bench.thread(person)
    attached = await turn_bench.attachment(
        person, "plan.md", b"# Plan\nShip in May.", "text/markdown"
    )
    picture = await turn_bench.attachment(person, "photo.png", PNG, "image/png")
    turn_bench.model.scripts = [saying("Noted.")]
    await turn_bench.ask(person, thread, "Keep these.", upload_ids=[attached, picture])
    turn_bench.model.calls.clear()
    turn_bench.model.scripts = [saying("In May.")]

    await turn_bench.ask(person, thread, "When do we ship?")

    request = turn_bench.model.calls[0]
    earlier = "".join(
        part.text
        for message in request.messages[1:-1]
        for part in message.parts
        if isinstance(part, TextPart)
    )
    assert "Ship in May." in earlier
    assert 'attached the image "photo.png"' in earlier
    assert not any(
        isinstance(part, ImagePart) for message in request.messages for part in message.parts
    )


async def test_the_whole_text_is_read_back_as_the_person_s_own_file(turn_bench: TurnBench) -> None:
    person = uuid.uuid4()
    thread = await turn_bench.thread(person)
    tail = "The end is here."
    body = ("x" * (DIGEST_CHARS + 10) + tail).encode()
    attached = await turn_bench.attachment(person, "notes.txt", body, "text/plain")

    def read_on(request: ChatRequest) -> list[ChatDelta]:
        text, _ = question_of(request)
        ref = text.split('result_ref "', 1)[1].split('"', 1)[0]
        arguments = json.dumps({"result_ref": ref, "cursor": DIGEST_CHARS})
        return calling(("core__read_result", arguments))

    turn_bench.model.scripts = [read_on, saying("Got it.")]

    await turn_bench.ask(person, thread, "Read all of it.", upload_ids=[attached])

    page = "".join(
        part.text
        for part in turn_bench.model.calls[1].messages[-1].parts
        if isinstance(part, TextPart)
    )
    assert tail in page
    assert "file:own" in page


async def test_attachments_come_only_with_a_new_question_and_only_one_s_own(
    turn_bench: TurnBench,
) -> None:
    person, stranger = uuid.uuid4(), uuid.uuid4()
    thread = await turn_bench.thread(person)
    theirs = await turn_bench.attachment(stranger, "secret.txt", b"not yours", "text/plain")
    first = stream_of(await turn_bench.ask(person, thread, "Hi."))

    foreign = await turn_bench.ask(person, thread, "Read it.", upload_ids=[theirs])
    again = await turn_bench.ask(
        person, thread, "Hi.", regenerate_of=first[0][2]["message_id"], upload_ids=[theirs]
    )
    many = await turn_bench.ask(
        person, thread, "Six.", upload_ids=[str(uuid.uuid4()) for _ in range(6)]
    )

    assert (foreign.status_code, foreign.json()["error"]["code"]) == (409, "upload_not_claimable")
    assert again.status_code == 422
    assert many.status_code == 422
