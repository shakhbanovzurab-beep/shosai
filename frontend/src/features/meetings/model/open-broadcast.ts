import { MOCK_API } from "@/config/unserved-slices";
import { ApiError } from "@/lib/api/errors";

import { broadcastApi, type LiveTicketOut } from "../api/broadcast-api";
import type { BroadcastSession, BroadcastTicket } from "../domain/broadcast";

/* Вход в трансляцию по ссылке и сама трансляция: на моках разработки — демо по токену ссылки, иначе — API и LiveKit. */

export type BroadcastMedia = { mic: boolean; camera: boolean; stream: MediaStream | null };

const ticketOf = (out: LiveTicketOut): BroadcastTicket => ({
  entry: out.entry,
  title: out.title,
  role: out.role,
  waitingRoom: out.waiting_room,
  identity: out.identity ?? "",
  access:
    out.livekit_url && out.livekit_token && out.room_pass
      ? { livekitUrl: out.livekit_url, livekitToken: out.livekit_token, roomPass: out.room_pass }
      : null,
  knock: out.knock,
  broadcastId: out.broadcast_id,
});

/** Что ссылка отвечает этому человеку; `name` — имя гостя. */
export async function enterBroadcast(token: string, name: string | null): Promise<BroadcastTicket> {
  if (!MOCK_API) return ticketOf(await broadcastApi.join(token, name));
  const { demoTicket } = await import("../data/demo-broadcast-entry");
  return demoTicket(token, name);
}

/** Зритель в зале ожидания спрашивает, впустили ли его. */
export async function knockAgain(token: string, ticket: BroadcastTicket): Promise<BroadcastTicket> {
  if (!MOCK_API) return ticketOf(await broadcastApi.knock(token, ticket.knock ?? ""));
  const { demoKnock } = await import("../data/demo-broadcast-entry");
  return demoKnock(token, ticket);
}

/** Открыть трансляцию: сцена — со своими устройствами из лобби, зал — без них. */
export async function openBroadcast(
  token: string,
  ticket: BroadcastTicket,
  self: { name: string; media: BroadcastMedia },
): Promise<BroadcastSession> {
  const media = ticket.role ? self.media : { mic: false, camera: false, stream: null };
  const setup = {
    token,
    identity: ticket.identity,
    name: self.name,
    role: ticket.role === "host" ? ("owner" as const) : ("participant" as const),
    title: ticket.title,
    marks: { notes: false, recording: false },
    link: `${window.location.origin}/live/${token}`,
    livekit: { url: ticket.access?.livekitUrl ?? "", token: ticket.access?.livekitToken ?? "" },
    roomPass: ticket.access?.roomPass ?? "",
    roomId: null,
    media,
  };
  if (MOCK_API) {
    const { DemoBroadcast } = await import("../data/demo-broadcast");
    return new DemoBroadcast({ title: ticket.title, role: ticket.role, waitingRoom: ticket.waitingRoom, call: setup });
  }
  if (!ticket.access) throw new ApiError("video_unavailable", 503, "video_unavailable");
  // livekit-client — отдельным чанком страниц комнаты и трансляции.
  const { LiveKitBroadcast } = await import("./livekit-broadcast");
  const broadcast = new LiveKitBroadcast(token, { ...ticket, access: ticket.access }, setup);
  try {
    await broadcast.connect();
  } catch {
    broadcast.leave();
    throw new ApiError("video_unavailable", 503, "video_unavailable");
  }
  return broadcast;
}
