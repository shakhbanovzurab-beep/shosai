/** Строка запроса как запись, повторённый ключ — списком: в таком виде её читают парсеры слайсов. */
export function searchRecord(params: URLSearchParams): Record<string, string | string[] | undefined> {
  const record: Record<string, string | string[]> = {};
  for (const key of new Set(params.keys())) {
    const values = params.getAll(key);
    record[key] = values.length === 1 ? values[0] : values;
  }
  return record;
}

/** Один параметр запроса строкой или undefined, если его нет. */
export const searchValue = (params: URLSearchParams, key: string) => params.get(key) ?? undefined;
