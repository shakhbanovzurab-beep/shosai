import { roomApi } from "../api/room-api";

/** Путь комнаты в кабинете по её приглашению: `https://…/meet/{token}` → `/app/meet/{token}`. */
export const roomPathOf = (link: string) => `/app/meet/${new URL(link).pathname.split("/").at(-1) ?? ""}`;

/** «Начать сейчас»: новая комната в Личном пространстве; повтор нажатия с тем же ключом — та же комната. */
export async function startMeeting(idempotencyKey: string): Promise<string> {
  const room = await roomApi.open(idempotencyKey);
  return roomPathOf(room.link);
}
