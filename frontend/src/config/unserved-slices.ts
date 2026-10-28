/**
 * Срезы сервера, у которых ещё нет API: экраны кабинета для них держатся на моках `npm run dev`. Там, где моков нет
 * (`npm run dev:api`, сборка), виджеты такого среза внутри чужих экранов не показываются — иначе они висели бы
 * ошибкой. Скрываются только срезы из этого списка: ошибки построенных срезов показываются как обычно. Срез уходит
 * из списка в том же изменении, что приносит его API.
 */
const UNSERVED_SLICES: ReadonlySet<string> = new Set(["calendar", "hubs"]);

/** Работает ли кабинет на моках разработки (`npm run dev`): то же условие, что в main.tsx; в сборке — false. */
export const MOCK_API = import.meta.env.DEV && import.meta.env.MODE !== "api";

/** Отвечает ли сейчас кому-то API среза сервера `slice`: настоящий или моки разработки. */
export const isServed = (slice: string) => MOCK_API || !UNSERVED_SLICES.has(slice);
