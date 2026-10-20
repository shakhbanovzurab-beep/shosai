/** Ключи React для строк, которые могут повторяться: сама строка и номер её повтора, а не место в списке. */
export function keyed(values: readonly string[]): { key: string; value: string }[] {
  const seen = new Map<string, number>();
  return values.map((value) => {
    const repeat = seen.get(value) ?? 0;
    seen.set(value, repeat + 1);
    return { key: `${value}#${repeat}`, value };
  });
}
