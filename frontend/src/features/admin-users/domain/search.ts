/** Что ищет администратор: сервер ищет либо по точной почте, либо по части имени, не по обоим сразу. */
export type UserSearch = { email: string } | { name: string };

const MAX_EMAIL = 254;
const MIN_NAME = 2;
const MAX_NAME = 80;

/** Строка поиска: с «@» — почта, иначе часть имени от двух знаков; null — искать пока нечего. */
export function userSearchOf(text: string): UserSearch | null {
  const query = text.trim();
  if (query.includes("@")) return query.length <= MAX_EMAIL ? { email: query } : null;
  return query.length >= MIN_NAME && query.length <= MAX_NAME ? { name: query } : null;
}
