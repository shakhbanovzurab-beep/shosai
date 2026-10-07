const CYRILLIC = "абвгдеёжзийклмнопрстуфхцчшщъыьэюя";
const LATIN = "a b v g d e e zh z i y k l m n o p r s t u f h ts ch sh sch _ y _ e yu ya".split(" ");
/** Cyrillic letter → Latin; "_" marks letters dropped from slugs (ъ, ь). */
const TRANSLIT = new Map([...CYRILLIC].map((char, index) => [char, LATIN[index] === "_" ? "" : LATIN[index]]));
const NON_SLUG = /[^a-z0-9]+/g;
const EDGE_DASHES = /^-+|-+$/g;

/** «Командный план» → «komandnyy-plan». */
export function slugify(name: string) {
  const latin = [...name.toLowerCase()].map((char) => TRANSLIT.get(char) ?? char).join("");
  return latin.replace(NON_SLUG, "-").replace(EDGE_DASHES, "").slice(0, 40);
}
