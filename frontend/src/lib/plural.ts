const russianRules = new Intl.PluralRules("ru-RU");

/** Picks the Russian word form for a count: `[one, few, many]`, e.g. ["участник", "участника", "участников"]. */
export function pluralizeRu(count: number, [one, few, many]: readonly [string, string, string]) {
  const rule = russianRules.select(count);
  if (rule === "one") return one;
  if (rule === "few") return few;
  return many;
}
