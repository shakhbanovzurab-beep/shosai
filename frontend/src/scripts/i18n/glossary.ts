/*
 * Reads the glossary the way people write it: GLOSSARY.md (the do-not-translate list and the typography
 * table) and glossary/<language>.md (the term table and the "Same as English" list).
 */

export interface TermRow {
  english: string;
  use: string;
  avoid: string[];
}

/** The lines of a `## Heading` section, up to the next `## `. */
export function section(markdown: string, heading: string): string[] {
  const lines = markdown.split("\n");
  const start = lines.findIndex((line) => line.trim() === `## ${heading}`);
  if (start === -1) return [];
  const end = lines.findIndex((line, index) => index > start && line.startsWith("## "));
  return lines.slice(start + 1, end === -1 ? undefined : end);
}

/** The cells of a Markdown table's body rows (header and separator dropped). */
export function tableRows(lines: string[]): string[][] {
  const rows = lines.filter((line) => line.trim().startsWith("|"));
  return rows.slice(2).map((row) =>
    row
      .trim()
      .replace(/^\||\|$/g, "")
      .split("|")
      .map((cell) => cell.trim()),
  );
}

/** Bullet items written as code: "- `Leo`". */
export const codeBullets = (lines: string[]) =>
  lines.map((line) => /^- `(.+)`\s*$/.exec(line.trim())?.[1]).filter((item): item is string => item !== undefined);

const codeSpans = (cell: string) => [...cell.matchAll(/`([^`]+)`/g)].map((match) => match[1]);

export interface StyleGuide {
  doNotTranslate: string[];
  /** Characters a language's messages must not contain, by language code. */
  notAllowed: Map<string, string[]>;
}

export function readStyleGuide(markdown: string): StyleGuide {
  const typography = section(markdown, "Typography by language");
  const header = typography.find((line) => line.trim().startsWith("|")) ?? "";
  const columns = header.split("|").map((cell) => cell.trim());
  const notAllowedColumn = columns.indexOf("Not allowed") - 1;
  const notAllowed = new Map<string, string[]>();
  for (const cells of tableRows(typography)) notAllowed.set(cells[0], codeSpans(cells[notAllowedColumn] ?? ""));
  return { doNotTranslate: codeBullets(section(markdown, "Do not translate")), notAllowed };
}

/** The English terms of glossary/terms.md, in order. */
export const readTermList = (markdown: string) => tableRows(markdown.split("\n")).map((cells) => cells[0]);

export interface LanguageGlossary {
  terms: TermRow[];
  sameAsEnglish: string[];
}

const splitAvoid = (cell: string) =>
  cell
    .split(",")
    .map((term) => term.trim())
    .filter((term) => term && term !== "—" && term !== "-");

export function readLanguageGlossary(markdown: string): LanguageGlossary {
  const terms = tableRows(section(markdown, "Terms")).map(([english, use, avoid]) => ({
    english,
    use,
    avoid: splitAvoid(avoid ?? ""),
  }));
  return { terms, sameAsEnglish: codeBullets(section(markdown, "Same as English")) };
}

/** A language glossary must name every term of the list, in order, each with a word to use. */
export function checkLanguageGlossary(glossary: LanguageGlossary, termList: string[]): string[] {
  const problems: string[] = [];
  const english = new Set(glossary.terms.map((row) => row.english));
  const listed = new Set(termList);
  for (const term of termList) if (!english.has(term)) problems.push(`lacks the term “${term}”`);
  for (const term of english) if (!listed.has(term)) problems.push(`has “${term}”, which terms.md doesn’t`);
  for (const row of glossary.terms) if (!row.use) problems.push(`gives no word to use for “${row.english}”`);
  return problems;
}
