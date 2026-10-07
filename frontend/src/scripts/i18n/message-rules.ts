import { type MessageShape, pluralCategories, readMessage } from "./icu";

/** What a language's messages are checked against, from GLOSSARY.md and glossary/<language>.md. */
export interface LanguageRules {
  language: string;
  doNotTranslate: string[];
  avoid: { term: string; use: string }[];
  sameAsEnglish: Set<string>;
  notAllowed: string[];
}

const escapeRegExp = (text: string) => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const LETTER = /\p{L}/u;
/** A quoted name from another product's interface (macOS's 「アプリケーション」 folder), cited as it reads there. */
const QUOTED = /“[^”]*”|„[^“]*“|«[^»]*»|「[^」]*」|『[^』]*』/gu;
const ACRONYMS = /^[\s\p{P}\p{S}\p{N}]*(\p{Lu}{2,6}[\s\p{P}\p{S}\p{N}]*)+$/u;
/** Languages written in Latin script, where a short label is often the same word as in English ("Status", "Live"). */
const LATIN_SCRIPT = new Set(["en", "fr", "de", "nl", "it", "es", "pt-BR", "tr", "vi", "id"]);
/** Languages that inflect a name with a plain -s (German "Leos Antworten"). */
const GENITIVE_S = new Set(["de", "nl"]);

/**
 * Whether a do-not-translate name appears as a whole word: "Leo", not "Leonardo". Only Latin letters and digits
 * count as touching it, so particles written straight after it in other scripts are fine ("Leoに", "Leo에게").
 */
export const containsName = (text: string, name: string) =>
  new RegExp(`(?<![\\p{Script=Latin}\\p{N}])${escapeRegExp(name)}(?![\\p{Script=Latin}\\p{N}])`, "u").test(text);

const difference = (a: Iterable<string>, b: Iterable<string>) => {
  const other = new Set(b);
  return [...a].filter((item) => !other.has(item));
};

function compareShapes(source: MessageShape, target: MessageShape, language: string): string[] {
  const problems: string[] = [];
  for (const missing of difference(source.arguments, target.arguments)) problems.push(`lacks {${missing}}`);
  for (const extra of difference(target.arguments, source.arguments)) problems.push(`has {${extra}}, English doesn’t`);
  for (const [name, options] of source.selects) {
    const theirs = target.selects.get(name);
    if (theirs && theirs.join() !== options.join())
      problems.push(`select {${name}} options ${theirs.join("/")} differ from English ${options.join("/")}`);
  }
  for (const plural of target.plurals) {
    const required = pluralCategories(language, plural.ordinal);
    const written = plural.options.filter((option) => !option.startsWith("="));
    const kind = plural.ordinal ? "selectordinal" : "plural";
    for (const category of difference(required, written))
      problems.push(`{${plural.name}, ${kind}} lacks “${category}”`);
    for (const category of difference(written, required))
      problems.push(`{${plural.name}, ${kind}} has “${category}”, which ${language} doesn’t use`);
  }
  return problems;
}

const CJK_PUNCTUATION = /[぀-ヿ㐀-鿿][,.:;?!]/u;
const DEVANAGARI_FULL_STOP = /[ऀ-ॿ]\.(?=\s|$)/u;
const FRENCH_SPACE = / [:;!?»]|« |[\p{L}\p{N}][;!?»]/u;

/** Typography of the words themselves: ICU syntax (commas in `{n, plural, …}`) is never looked at. */
function checkTypography(text: string[], rules: LanguageRules): string[] {
  const problems = new Set<string>();
  for (const run of text) {
    if (run.includes("...")) problems.add("uses ... instead of …");
    if (run.includes("'")) problems.add("uses ' instead of ’");
    for (const character of rules.notAllowed)
      if (run.includes(character)) problems.add(`uses ${character}, not used in ${rules.language}`);
    if (rules.language === "fr" && FRENCH_SPACE.test(run))
      problems.add("needs a no-break space (U+202F) before : ; ! ? » and after «");
    if (rules.language === "hi" && DEVANAGARI_FULL_STOP.test(run)) problems.add("ends a sentence with . instead of ।");
    if ((rules.language === "ja" || rules.language === "zh-Hant") && CJK_PUNCTUATION.test(run))
      problems.add("uses half-width punctuation after CJK text; use full-width");
  }
  return [...problems];
}

function checkWording(source: string, target: string, shape: MessageShape, rules: LanguageRules): string[] {
  const problems: string[] = [];
  const words = shape.text.join(" ");
  const keeps = (name: string) =>
    containsName(target, name) || (GENITIVE_S.has(rules.language) && containsName(target, `${name}s`));
  for (const name of rules.doNotTranslate)
    if (containsName(source, name) && !keeps(name)) problems.push(`must keep “${name}” as is`);
  // Names are exempt from the glossary: an avoided "workspace" must not trip on "Google Workspace".
  const own = rules.doNotTranslate.reduce((rest, name) => rest.replaceAll(name, ""), words);
  const lowered = own.toLocaleLowerCase(rules.language);
  // Code-like tokens copied from the English text ("owner/repo", "file.md") are formats, not word choices.
  const codes = source.split(/\s+/).filter((token) => /[/._@:]/.test(token) && target.includes(token));
  const prose = codes
    .reduce((rest, token) => rest.replaceAll(token.toLocaleLowerCase(rules.language), " "), lowered)
    .replace(QUOTED, " ");
  for (const { term, use } of rules.avoid)
    if (prose.indexOf(term.toLocaleLowerCase(rules.language)) !== -1)
      problems.push(`uses “${term}”; the glossary says “${use}”`);
  if (rules.language !== "en" && target === source && !rules.sameAsEnglish.has(target)) {
    // Acronyms (CRM, JSON) read the same everywhere, and in Latin-script languages so do many one- or two-word
    // labels; a whole sentence left in English is still caught.
    const shortLabel = LATIN_SCRIPT.has(rules.language) && own.trim().split(/\s+/).length <= 2;
    if (LETTER.test(own) && !ACRONYMS.test(own) && !shortLabel)
      problems.push("is the same as English (translate it, or list it under “Same as English”)");
  }
  return problems;
}

/** Everything wrong with one message of `rules.language`, compared with its English source. */
export function checkMessage(source: string, target: string, rules: LanguageRules): string[] {
  if (!target.trim()) return ["is empty"];
  const read = readMessage(target);
  if ("error" in read) return [`isn’t valid ICU (${read.error})`];
  const problems: string[] = [];
  if (/^\s/.test(target) !== /^\s/.test(source) || /\s$/.test(target) !== /\s$/.test(source))
    problems.push("starts or ends with whitespace differently from English");
  const english = readMessage(source);
  if ("shape" in english) problems.push(...compareShapes(english.shape, read.shape, rules.language));
  problems.push(...checkWording(source, target, read.shape, rules));
  problems.push(...checkTypography(read.shape.text, rules));
  return problems;
}
