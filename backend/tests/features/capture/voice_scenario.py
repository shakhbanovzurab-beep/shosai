"""A Gemini Live conversation for the voice route's tests, on the local live server.

At the person's first audio Gemini hears a question and calls `notes__search`; once the tool
answers it speaks, says what it said and ends its turn with usage. The server then waits
for the session to close.
"""

from websockets.asyncio.server import ServerConnection
from websockets.exceptions import ConnectionClosed

from tests.core.ai.live_scenarios import SPOKEN, send
from tests.doubles.live_server import Json, LiveServer, Scenario

QUESTION = "What about the budget?"
ANSWER = "Travel was cut by a fifth."
USAGE: Json = {
    "promptTokensDetails": [{"modality": "AUDIO", "tokenCount": 50}],
    "responseTokensDetails": [{"modality": "AUDIO", "tokenCount": 50}],
}


async def until_message(connection: ServerConnection, server: LiveServer, *keys: str) -> Json:
    """The next message of the client that carries one of the keys."""
    while True:
        message = await server.receive(connection)
        if any(key in message for key in keys):
            return message


def budget_question() -> Scenario:
    """The person asks about the budget, Leo reads notes and answers by voice."""

    async def run(connection: ServerConnection, server: LiveServer) -> None:
        await server.receive(connection)
        await send(connection, {"setupComplete": {}})
        try:
            await until_message(connection, server, "realtimeInput", "realtime_input")
            await send(connection, {"serverContent": {
                "inputTranscription": {"text": QUESTION, "finished": True}}})  # fmt: skip
            call = {"id": "call-1", "name": "notes__search", "args": {"query": "budget"}}
            await send(connection, {"toolCall": {"functionCalls": [call]}})
            await until_message(connection, server, "toolResponse", "tool_response")
            await send(connection, {"serverContent": {
                "outputTranscription": {"text": ANSWER, "finished": True}}})  # fmt: skip
            speech = {"inlineData": {"mimeType": "audio/pcm;rate=24000", "data": SPOKEN}}
            await send(connection, {"serverContent": {"modelTurn": {"parts": [speech]}}})
            await send(
                connection, {"serverContent": {"turnComplete": True}, "usageMetadata": USAGE}
            )
            while True:
                await server.receive(connection)
        except ConnectionClosed:
            return

    return run
