/*
 * Ресурсы по домену данных (`tasks`, `notes`, `files` — имена доменов сервера). Когда данные домена меняет не этот
 * экран — например, Leo выполнил одобренное действие и назвал, что оно изменило, — показанные ресурсы домена
 * перечитываются; непоказанные перечитаются сами, когда их покажут. Вернулся человек на вкладку — перечитываются
 * все показанные: пока её не было видно, данные могли изменить на другом устройстве, в другой вкладке или в фоне.
 */

interface Watchable {
  refreshIfWatched(): Promise<void>;
}

const domains = new Map<string, Set<Watchable>>();

/** Отнести ресурс к домену данных; возвращает тот же ресурс. */
export function inDomain<R extends Watchable>(domain: string, resource: R): R {
  const known = domains.get(domain);
  if (known) known.add(resource);
  else domains.set(domain, new Set([resource]));
  return resource;
}

/** Перечитать показанные ресурсы этих доменов; незнакомый домен ничего не перечитывает. */
export function refreshDomains(changed: readonly string[]) {
  for (const domain of new Set(changed))
    for (const resource of domains.get(domain) ?? []) void resource.refreshIfWatched();
}

/** Перечитать все показанные ресурсы всех доменов. */
export function refreshWatched() {
  const resources = new Set([...domains.values()].flatMap((known) => [...known]));
  for (const resource of resources) void resource.refreshIfWatched();
}

/** Перечитывать показанные ресурсы, когда вкладка снова видна; возвращает отписку. */
export function refreshOnReturn() {
  const onVisible = () => {
    if (document.visibilityState === "visible") refreshWatched();
  };
  document.addEventListener("visibilitychange", onVisible);
  return () => document.removeEventListener("visibilitychange", onVisible);
}
