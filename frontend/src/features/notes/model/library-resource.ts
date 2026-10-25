import { usePollingResource } from "@/hooks/use-polling-resource";
import { createPollingResource, type PollingResource } from "@/lib/polling-resource";
import { inDomain } from "@/lib/resource-domains";

import { notesApi } from "../api/notes-api";
import { isBusyCard, type LibraryFolder, type MeetingCard } from "../domain/library";
import { cardOf } from "./library-cards";

/*
 * Библиотека постранично по курсору сервера: первая страница грузится сразу, следующие — по кнопке. Пока
 * какая-то встреча идёт или её записи пишутся, первая страница перечитывается каждые 1,5 с; дочитанные дальше
 * страницы при этом сохраняются. Удалённая встреча скрыта во всех списках, пока ждёт «Отменить».
 */

const PAGE = 50;

export interface LibraryPages {
  readonly items: readonly MeetingCard[];
  readonly nextCursor: string | null;
}

const ALL = "all";
const libraries = new Map<string, PollingResource<LibraryPages>>();
/** Встречи, удалённые в этом окне, пока тост с «Отменить» не закрылся. */
export const pendingDeletes = new Set<string>();

const visible = (items: readonly MeetingCard[]) => items.filter((card) => !pendingDeletes.has(card.id));

/** Порядок сервера: новее раньше, при равном начале — больший id. */
const before = (a: MeetingCard, b: MeetingCard) =>
  a.startedAt === b.startedAt ? a.id > b.id : a.startedAt > b.startedAt;

/** Свежая первая страница поверх уже дочитанных: хвост сохраняется, если он дальше первой страницы. */
export function merged(
  previous: LibraryPages | null,
  fresh: readonly MeetingCard[],
  cursor: string | null,
): LibraryPages {
  const last = fresh.at(-1);
  if (!previous || !last || previous.items.length <= fresh.length) return { items: fresh, nextCursor: cursor };
  const ids = new Set(fresh.map((card) => card.id));
  const tail = previous.items.filter((card) => !ids.has(card.id) && before(last, card));
  return tail.length > 0
    ? { items: [...fresh, ...tail], nextCursor: previous.nextCursor }
    : { items: fresh, nextCursor: cursor };
}

function libraryOf(folder: LibraryFolder | undefined): PollingResource<LibraryPages> {
  const key = folder ?? ALL;
  const existing = libraries.get(key);
  if (existing) return existing;
  const resource: PollingResource<LibraryPages> = inDomain(
    "notes",
    createPollingResource(
      async () => {
        const page = await notesApi.page({ folder, limit: PAGE });
        const state = resource.getSnapshot();
        return merged(
          state.status === "ready" ? state.data : null,
          visible(page.items.map(cardOf)),
          page.next_cursor ?? null,
        );
      },
      (data) => data.items.some(isBusyCard),
    ),
  );
  libraries.set(key, resource);
  return resource;
}

export const useLibrary = (folder: LibraryFolder | undefined) => usePollingResource(libraryOf(folder));
export const retryLibrary = (folder: LibraryFolder | undefined) => libraryOf(folder).refresh();

/** Следующая страница библиотеки, если она есть. */
export async function loadMore(folder: LibraryFolder | undefined) {
  const resource = libraryOf(folder);
  const state = resource.getSnapshot();
  if (state.status !== "ready" || state.data.nextCursor === null) return;
  const page = await notesApi.page({ folder, cursor: state.data.nextCursor, limit: PAGE });
  resource.update((data) => {
    const ids = new Set(data.items.map((card) => card.id));
    const more = visible(page.items.map(cardOf)).filter((card) => !ids.has(card.id));
    return { items: [...data.items, ...more], nextCursor: page.next_cursor ?? null };
  });
}

/** Меняет карточку во всех открытых списках; `keep` решает, остаётся ли она в списке своей папки. */
export function patchCard(id: string, change: (card: MeetingCard) => MeetingCard) {
  for (const [key, resource] of libraries) {
    if (resource.getSnapshot().status !== "ready") continue;
    resource.update((data) => ({
      ...data,
      items: data.items.flatMap((card) => {
        if (card.id !== id) return [card];
        const next = change(card);
        return key === ALL || key === (next.folderId ?? "none") ? [next] : [];
      }),
    }));
  }
}

/** Убирает карточку из всех открытых списков, не дожидаясь сервера. */
export function dropCard(id: string) {
  for (const resource of libraries.values())
    if (resource.getSnapshot().status === "ready")
      resource.update((data) => ({ ...data, items: data.items.filter((card) => card.id !== id) }));
}

/** Перечитывает все открытые списки: после удаления папки или сбоя изменения. */
export function refreshLibraries() {
  for (const resource of libraries.values()) void resource.refresh();
}

/** Все открытые библиотеки, прочитанные заново уже после изменения: в них есть только что созданная встреча. */
export async function reloadLibraries() {
  await Promise.all([...libraries.values()].map((resource) => resource.reload()));
}
