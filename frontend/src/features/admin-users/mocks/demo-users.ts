import type { AdminUser, AdminUserCard } from "../domain/contract";

// Примерные люди админки в `npm run dev` без бэкенда: оба дома, все состояния, что видит администратор.
const people: AdminUser[] = [
  ["Иван Петров", "ivan.petrov@example.ru", "ru", "active", "2026-09-28T08:12:00Z", "2026-10-14T19:40:00Z"],
  ["Мария Смирнова", "maria.smirnova@example.ru", "ru", "frozen", "2026-08-03T10:00:00Z", "2026-10-01T09:15:00Z"],
  ["Anna Schmidt", "anna.schmidt@example.de", "eu", "active", "2026-07-21T14:30:00Z", "2026-10-15T06:05:00Z"],
  ["João Silva", "joao.silva@example.pt", "eu", "deletion_scheduled", "2026-06-11T12:00:00Z", "2026-10-10T18:00:00Z"],
  ["Иван Сидоров", "ivan.sidorov@example.com", "eu", "banned", "2026-05-02T07:45:00Z", null],
].map(([full_name, email, home, state, created_at, last_login_at], index) => ({
  id: `00000000-0000-4000-8000-00000000000${index + 1}`,
  full_name: full_name as string,
  display_name: null,
  email: email as string,
  home: home as string,
  state: state as AdminUser["state"],
  created_at: created_at as string,
  last_login_at: last_login_at as string | null,
}));

export function findUsers(email: string | null, name: string | null): AdminUser[] {
  const text = (email ?? name ?? "").toLowerCase();
  const found = email
    ? people.filter((person) => person.email === text)
    : people.filter((person) => person.full_name.toLowerCase().includes(text));
  return found.toSorted((a, b) => b.created_at.localeCompare(a.created_at));
}

export function cardOf(id: string): AdminUserCard | null {
  const user = people.find((person) => person.id === id);
  if (!user) return null;
  const live = user.state === "active";
  return {
    user,
    work_role: user.home === "ru" ? "Руководитель проектов" : "Product designer",
    country: user.home === "ru" ? "RU" : "DE",
    language: user.home === "ru" ? "ru" : "en",
    timezone: user.home === "ru" ? "Europe/Moscow" : "Europe/Berlin",
    email_verified_at: user.created_at,
    sessions: live
      ? [
          {
            id: `${id}-s1`,
            client_kind: "web",
            device_label: "Chrome · macOS",
            ip: "203.0.113.7",
            created_at: "2026-10-12T08:00:00Z",
            last_used_at: user.last_login_at ?? user.created_at,
          },
        ]
      : [],
    sign_ins: user.last_login_at
      ? [
          { created_at: user.last_login_at, outcome: "success", client_kind: "web", ip: "203.0.113.7" },
          { created_at: "2026-10-09T21:02:00Z", outcome: "wrong_password", client_kind: "desktop", ip: "198.51.100.4" },
        ]
      : [],
    spend: live
      ? { today_usd: "0.0412", week_usd: "0.8731", month_usd: "3.1290" }
      : { today_usd: "0", week_usd: "0", month_usd: "0" },
  };
}

/** Блокировка и разблокировка меняют состояние в памяти вкладки. */
export function setState(id: string, state: AdminUser["state"]): void {
  const user = people.find((person) => person.id === id);
  if (user) user.state = state;
}
