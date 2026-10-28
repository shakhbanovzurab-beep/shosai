import type { components } from "@/lib/api/generated/schema";
import { type MockRoute, mockRoute } from "@/mocks/routing";

/*
 * Моки входа в комнату и «Новой встречи» для `npm run dev` и тестов. Токен ссылки выбирает ответ: `ended`, `full`,
 * `removed`, `unavailable` и `missing` — отказы сервера; `own-…` — своя комната; любой другой — чужая.
 */

type JoinOut = components["schemas"]["JoinOut"];
type RoomOut = components["schemas"]["RoomOut"];
type TokenParams = { params: Promise<{ token: string }> };

const REFUSALS: Record<string, [number, string]> = {
  ended: [410, "room_finished"],
  full: [409, "room_full"],
  removed: [403, "removed"],
  unavailable: [503, "video_unavailable"],
  missing: [404, "not_found"],
};

const refused = (status: number, code: string) =>
  Response.json({ error: { code, request_id: "mock-request" }, detail: code }, { status });

const hex = (length: number) =>
  Array.from(crypto.getRandomValues(new Uint8Array(length)), (byte) => (byte % 16).toString(16)).join("");

const joinRoute = {
  async POST(request: Request, { params }: TokenParams) {
    const { token } = await params;
    const refusal = REFUSALS[token];
    if (refusal) return refused(...refusal);
    const body = (await request.json().catch(() => ({}))) as { name?: string };
    const signedIn = request.headers.has("authorization");
    if (!signedIn && !body.name?.trim()) return refused(422, "name_required");
    const owner = token.startsWith("own-");
    const joined: JoinOut = {
      room: { title: owner ? null : "Design review", notes_on: true, recording: token === "recorded" },
      livekit_url: "wss://rtc.shosai.example",
      livekit_token: "mock-livekit-token",
      room_pass: `mock-pass-${hex(8)}`,
      pass_expires_at: new Date(Date.now() + 12 * 3_600_000).toISOString(),
      identity: `${signedIn ? crypto.randomUUID() : `guest-${hex(12)}`}__${hex(8)}`,
      role: owner ? "owner" : "participant",
      ceiling: 50,
      room_id: owner ? crypto.randomUUID() : null,
    };
    return Response.json(joined);
  },
};

const roomsRoute = {
  async POST() {
    const room: RoomOut = {
      id: crypto.randomUUID(),
      title: null,
      state: "open",
      notes_on: true,
      workspace_id: null,
      link: `https://shosai.tech/meet/own-${hex(8)}`,
      created_at: new Date().toISOString(),
      closed_at: null,
      call: null,
    };
    return Response.json(room, { status: 201 });
  },
};

export const handlers: MockRoute[] = [
  mockRoute("/v1/meetings/join/:token", joinRoute, ["POST"]),
  mockRoute("/v1/meetings/rooms", roomsRoute, ["POST"]),
];
