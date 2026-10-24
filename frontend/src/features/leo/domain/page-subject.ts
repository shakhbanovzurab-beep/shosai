/*
 * Что открыто на странице, о которой человек спрашивает Leo (agent §3.3, `surface.subject`): встреча, задача, доска.
 * Сервер расскажет о ней модели через срез-владелец и только то, что человек может читать. Идентификатор — только
 * UUID: другое значение в адресе Leo не передаётся.
 */

export type SubjectKind = "meeting" | "task" | "board" | "file";

export interface PageSubject {
  readonly kind: SubjectKind;
  readonly id: string;
}

const UUID = /^[\da-f]{8}-[\da-f]{4}-[\da-f]{4}-[\da-f]{4}-[\da-f]{12}$/i;
const MEETING_PAGES = [/^\/app\/notes\/([^/]+)$/, /^\/app\/w\/[^/]+\/meetings\/([^/]+)$/];

const subject = (kind: SubjectKind, id: string | null | undefined): PageSubject | null =>
  id && UUID.test(id) ? { kind, id: id.toLowerCase() } : null;

/** Предмет страницы по её адресу и строке запроса; null, если страница ничего одного не показывает. */
export function pageSubject(path: string, search: string): PageSubject | null {
  for (const page of MEETING_PAGES) {
    const match = path.match(page);
    if (match) return subject("meeting", decodeURIComponent(match[1]));
  }
  if (path === "/app/kanban" || /^\/app\/w\/[^/]+\/tasks$/.test(path)) {
    const params = new URLSearchParams(search);
    return subject("task", params.get("task")) ?? subject("board", params.get("board"));
  }
  return null;
}
