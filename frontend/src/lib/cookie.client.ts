// Работа с cookie в браузере: кабинет — чисто браузерное приложение, все cookie читаются и пишутся здесь.

function writeClientCookie(serializedCookie: string) {
  // biome-ignore lint/suspicious/noDocumentCookie: This project still uses document.cookie for broad browser support.
  document.cookie = serializedCookie;
}

export function setClientCookie(key: string, value: string, days = 7) {
  const expires = new Date(Date.now() + days * 864e5).toUTCString();
  writeClientCookie(`${key}=${value}; expires=${expires}; path=/`);
}

/** Значение cookie этой страницы или null. */
export function readClientCookie(key: string): string | null {
  const prefix = `${key}=`;
  const entry = document.cookie.split("; ").find((part) => part.startsWith(prefix));
  return entry ? decodeURIComponent(entry.slice(prefix.length)) : null;
}
