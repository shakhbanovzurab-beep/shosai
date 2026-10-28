import type { CallPerson } from "../domain/call";

/* Люди демо-звонка: имена такие, как их ввели участники, поэтому одинаковы на всех языках интерфейса. */

const NAMES = ["Anna Petrova", "Igor Kim", "Maria Lopez", "David Chen", "Lena Fischer", "Omar Haddad", "Yuki Sato"];

const hex = (value: number, width: number) => value.toString(16).padStart(width, "0").slice(-width);

/** Сессия демо-участника: identity в форме сервера `<принципал>__<8 hex>`. */
export function demoPerson(index: number, extra: Partial<CallPerson> = {}): CallPerson {
  const base = NAMES[index % NAMES.length] ?? "Guest";
  const lap = Math.floor(index / NAMES.length);
  return {
    identity: `guest-${hex(index + 1, 12)}__${hex(index * 7919 + 17, 8)}`,
    name: lap === 0 ? base : `${base} ${lap + 1}`,
    isLocal: false,
    isOwner: false,
    micOn: index % 3 !== 2,
    cameraOn: index % 4 !== 3,
    screenOn: false,
    speaking: false,
    lastSpokeAt: 0,
    hand: null,
    ...extra,
  };
}

/** Сколько людей в демо-звонке по токену ссылки: `big` показывает звонок на 50. */
export const demoCrowd = (token: string) => (token === "big" ? 49 : 4);
