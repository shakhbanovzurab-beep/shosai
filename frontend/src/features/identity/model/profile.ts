import { browserTimeZone } from "@/i18n/time-zone";
import { ApiError } from "@/lib/api/errors";

import { deleteAvatar, type MePatch, patchMe, putAvatar } from "../api/profile-api";
import type { Me } from "../domain/session";
import { sessionState, updateSession } from "./session-store";

export type ConsentsPatch = NonNullable<MePatch["consents"]>;

/**
 * Изменить профиль сразу на экране и сохранить: при отказе сервера прежние значения возвращаются, а ошибка
 * уходит вызывающему, чтобы он сказал о ней.
 */
async function optimistic(apply: (me: Me) => Me, save: () => Promise<Me>): Promise<Me> {
  const before = sessionState().me;
  if (before !== null) updateSession({ me: apply(before) });
  try {
    const saved = await save();
    updateSession({ me: saved });
    return saved;
  } catch (error) {
    if (before !== null) updateSession({ me: before });
    throw error;
  }
}

type ProfileFields = Pick<MePatch, "full_name" | "display_name" | "work_role">;

/** Имя, обращение для Leo, род занятий — сохраняются, как только изменены. */
export function saveProfile(change: ProfileFields): Promise<Me> {
  return optimistic(
    (me) => ({ ...me, ...change, full_name: change.full_name ?? me.full_name }),
    () => patchMe({ ...change, cross_border_warning_confirmed: false }),
  );
}

/**
 * Согласия. Отзыв трансграничной передачи останавливает ИИ для аккаунта в российском доме, поэтому сервер
 * требует подтверждённого предупреждения (`warningConfirmed`).
 */
export function saveConsents(consents: ConsentsPatch, warningConfirmed = false): Promise<Me> {
  const given = Object.fromEntries(
    Object.entries(consents).filter(([, value]) => value !== null && value !== undefined),
  );
  return optimistic(
    (me) => ({ ...me, consents: { ...me.consents, ...given } }),
    () => patchMe({ consents, cross_border_warning_confirmed: warningConfirmed }),
  );
}

/**
 * Пояс из Settings › Account: `null` — «Автоматически», пояс следует за браузером; выбранный вручную пояс
 * фиксируется и больше сам не меняется (ADR 0058).
 */
export function saveTimeZone(zone: string | null): Promise<Me> {
  const change =
    zone === null ? { timezone: browserTimeZone(), timezone_auto: true } : { timezone: zone, timezone_auto: false };
  return optimistic(
    (me) => ({ ...me, ...change }),
    () => patchMe({ ...change, cross_border_warning_confirmed: false }),
  );
}

/**
 * Вход в кабинет в режиме «Автоматически»: пояс браузера сохраняется в профиль, если отличается, — по нему
 * сервер и Leo считают время человека. Кабинет в этом режиме и так печатает время в поясе браузера, поэтому
 * отказ сервера здесь не мешает работе: профиль догонит браузер при следующем входе.
 */
export async function followBrowserZone(me: Me): Promise<void> {
  const zone = browserTimeZone();
  if (!me.timezone_auto || me.timezone === zone) return;
  try {
    updateSession({ me: await patchMe({ timezone: zone, cross_border_warning_confirmed: false }) });
  } catch (error) {
    // Сеть (TypeError) или отказ сервера (незнакомый ему пояс): пробуем при следующем входе.
    if (!(error instanceof ApiError || error instanceof TypeError)) throw error;
  }
}

/** Новый аватар; изображение браузер уже обрезал и уменьшил. */
export async function setAvatar(image: Blob): Promise<Me> {
  const saved = await putAvatar(image);
  updateSession({ me: saved });
  return saved;
}

export async function clearAvatar(): Promise<Me> {
  const saved = await deleteAvatar();
  updateSession({ me: saved });
  return saved;
}
