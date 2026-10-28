import { MOCK_API } from "@/config/unserved-slices";
import { ApiError } from "@/lib/api/errors";

import type { BroadcastSession, BroadcastTicket } from "../domain/broadcast";

/*
 * Вход в трансляцию по ссылке и сама трансляция. На моках разработки — демо по токену ссылки; на сервере маршруты
 * трансляций появятся в A12b, а экраны встанут на них в A12c — до тех пор ссылка честно отвечает «недоступно».
 */

export type BroadcastMedia = { mic: boolean; camera: boolean; stream: MediaStream | null };

const unavailable = () => new ApiError("video_unavailable", 503, "video_unavailable");

/** Что ссылка отвечает этому человеку; `name` — имя гостя. */
export async function enterBroadcast(token: string, name: string | null): Promise<BroadcastTicket> {
  if (!MOCK_API) throw unavailable();
  const { demoTicket } = await import("../data/demo-broadcast-entry");
  return demoTicket(token, name);
}

/** Зритель в зале ожидания спрашивает, впустили ли его. */
export async function knockAgain(token: string, ticket: BroadcastTicket): Promise<BroadcastTicket> {
  if (!MOCK_API) throw unavailable();
  const { demoKnock } = await import("../data/demo-broadcast-entry");
  return demoKnock(token, ticket);
}

/** Открыть трансляцию: сцена — со своими устройствами из лобби, зал — без них. */
export async function openBroadcast(
  token: string,
  ticket: BroadcastTicket,
  self: { name: string; media: BroadcastMedia },
): Promise<BroadcastSession> {
  if (!MOCK_API) throw unavailable();
  const { DemoBroadcast } = await import("../data/demo-broadcast");
  return new DemoBroadcast({
    title: ticket.title,
    role: ticket.role,
    waitingRoom: ticket.waitingRoom,
    call: {
      token,
      identity: ticket.identity,
      name: self.name,
      role: ticket.role === "host" ? "owner" : "participant",
      title: ticket.title,
      marks: { notes: false, recording: false },
      link: `${window.location.origin}/live/${token}`,
      livekit: { url: "", token: "" },
      roomPass: "",
      roomId: null,
      media: ticket.role ? self.media : { mic: false, camera: false, stream: null },
    },
  });
}
