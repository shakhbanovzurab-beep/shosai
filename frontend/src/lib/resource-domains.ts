/*
 * Ресурсы по домену данных (`tasks`, `notes`, `files` — имена доменов сервера). Когда данные домена меняет не этот
 * экран — например, Leo выполнил одобренное действие и назвал, что оно изменило, — показанные ресурсы домена
 * перечитываются; непоказанные перечитаются сами, когда их покажут.
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
