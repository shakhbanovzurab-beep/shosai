/** Часть загрузки, как её подписал сервер: номер (с 1), точная длина и куда её положить PUT-запросом. */
export type PartLink = {
  number: number;
  size_bytes: number;
  url: string;
  headers: Record<string, string>;
};

/** Где в файле лежат байты каждой части: части идут друг за другом по порядку номеров. */
export function partRanges(parts: readonly Pick<PartLink, "number" | "size_bytes">[]): Map<number, [number, number]> {
  const ranges = new Map<number, [number, number]>();
  let start = 0;
  for (const part of parts.toSorted((a, b) => a.number - b.number)) {
    ranges.set(part.number, [start, start + part.size_bytes]);
    start += part.size_bytes;
  }
  return ranges;
}
