// Демо-человек моков identity: профиль, согласия и аватар меняются запросами и живут до перезагрузки страницы.
import type { components } from "@/lib/api/generated/schema";
import { LANGUAGE_COOKIE } from "@/lib/language";

type Me = components["schemas"]["Me"];
type MePatch = components["schemas"]["MePatch"];

function interfaceLanguage(): string {
  const entry = document.cookie.split("; ").find((part) => part.startsWith(`${LANGUAGE_COOKIE}=`));
  return entry ? decodeURIComponent(entry.slice(LANGUAGE_COOKIE.length + 1)) : "en";
}

let person: Omit<Me, "language"> = {
  id: "00000000-0000-7000-8000-000000000001",
  email: "arham@lumen.so",
  full_name: "Arham Khan",
  display_name: null,
  work_role: null,
  avatar_url: null,
  timezone: "Europe/Amsterdam",
  country: "NL",
  home: "eu",
  consents: { personal_data: true, cross_border: true, marketing: false, improve_models: false, share_location: false },
  operator_roles: ["owner"],
  created_at: "2026-01-01T00:00:00Z",
};

/** Профиль, как его отдал бы `GET /v1/me`; язык — из cookie интерфейса. */
export function demoMe(): Me {
  return { ...person, language: interfaceLanguage() };
}

/** Применить `PATCH /v1/me`; `null` в полях — «не менять», как на сервере. */
export function applyPatch(change: MePatch): Me {
  const consents = Object.fromEntries(Object.entries(change.consents ?? {}).filter(([, value]) => value !== null));
  person = {
    ...person,
    full_name: change.full_name ?? person.full_name,
    display_name: change.display_name ?? person.display_name,
    work_role: change.work_role ?? person.work_role,
    consents: { ...person.consents, ...consents },
  };
  return demoMe();
}

export function setAvatarUrl(url: string | null): Me {
  person = { ...person, avatar_url: url };
  return demoMe();
}
