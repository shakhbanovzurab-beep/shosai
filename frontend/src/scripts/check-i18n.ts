// Checks the message catalogs against English and the glossary, and the localized source against the
// source rules. Run: npm run i18n:check. See src/i18n/GLOSSARY.md and docs/i18n.md.

import { NAMESPACES } from "../i18n/namespaces";
import { DEFAULT_LANGUAGE, LANGUAGE_CODES } from "../lib/language";
import { type Catalog, compareKeys, readLanguage } from "./i18n/catalogs";
import { checkLanguageGlossary, readLanguageGlossary, readStyleGuide, readTermList } from "./i18n/glossary";
import { ADMIN_ONLY_SOURCES, LOCALIZED_SOURCES } from "./i18n/localized-sources";
import { checkMessage, type LanguageRules } from "./i18n/message-rules";
import { scanSource } from "./i18n/source-rules";
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, resolve } from "node:path";

const ROOT = resolve(import.meta.dirname, "../..");
const I18N = join(ROOT, "src/i18n");
const MESSAGES = join(I18N, "messages");
const problems: string[] = [];
const report = (where: string, message: string) => problems.push(`${where}: ${message}`);
const read = (path: string) => readFileSync(path, "utf8");
const at = (path: string) => relative(ROOT, path);

const styleGuide = readStyleGuide(read(join(I18N, "GLOSSARY.md")));
const termList = readTermList(read(join(I18N, "glossary/terms.md")));
const english = readLanguage(MESSAGES, DEFAULT_LANGUAGE) ?? new Map<string, Catalog>();

// The namespaces the app loads are exactly the English files, and every language has a folder.
const englishNamespaces = [...english.keys()];
for (const namespace of NAMESPACES)
  if (!english.has(namespace)) report("src/i18n/namespaces.ts", `${namespace}: no ${namespace}.json in English`);
for (const namespace of englishNamespaces)
  if (!(NAMESPACES as readonly string[]).includes(namespace))
    report("src/i18n/namespaces.ts", `${namespace}.json is not listed in NAMESPACES`);
for (const folder of readdirSync(MESSAGES))
  if (!(LANGUAGE_CODES as readonly string[]).includes(folder))
    report(at(join(MESSAGES, folder)), "not an interface language");

function rulesFor(language: string): LanguageRules {
  const rules: LanguageRules = {
    language,
    doNotTranslate: styleGuide.doNotTranslate,
    avoid: [],
    sameAsEnglish: new Set(),
    notAllowed: styleGuide.notAllowed.get(language) ?? [],
  };
  if (!styleGuide.notAllowed.has(language)) report("src/i18n/GLOSSARY.md", `no typography row for ${language}`);
  if (language === DEFAULT_LANGUAGE) return rules;
  const path = join(I18N, "glossary", `${language}.md`);
  if (!existsSync(path)) {
    report(at(path), "missing: every language needs its glossary");
    return rules;
  }
  const glossary = readLanguageGlossary(read(path));
  for (const problem of checkLanguageGlossary(glossary, termList)) report(at(path), problem);
  rules.avoid = glossary.terms.flatMap(({ use, avoid }) => avoid.map((term) => ({ term, use })));
  rules.sameAsEnglish = new Set(glossary.sameAsEnglish);
  return rules;
}

let messageCount = 0;
for (const language of LANGUAGE_CODES) {
  const catalogs = readLanguage(MESSAGES, language);
  if (!catalogs) {
    report(at(join(MESSAGES, language)), "missing: every interface language needs its catalogs");
    continue;
  }
  const rules = rulesFor(language);
  for (const catalog of catalogs.values()) for (const problem of catalog.problems) report(at(catalog.path), problem);
  if (language !== DEFAULT_LANGUAGE)
    for (const problem of compareKeys(english, catalogs)) report(`${at(join(MESSAGES, language))}`, problem);
  for (const [namespace, catalog] of catalogs) {
    const source = english.get(namespace);
    for (const [key, message] of catalog.messages) {
      const original = source?.messages.get(key);
      if (original === undefined) continue;
      messageCount += 1;
      for (const problem of checkMessage(original, message, rules)) report(`${at(catalog.path)} ${key}`, problem);
    }
  }
}

// Localized source: walk each listed file or folder.
const sourceFiles: string[] = [];
const collect = (path: string) => {
  if (!existsSync(path)) return report(at(path), "listed in LOCALIZED_SOURCES but doesn’t exist");
  if (statSync(path).isDirectory()) for (const name of readdirSync(path)) collect(join(path, name));
  else if (
    /\.tsx?$/.test(path) &&
    !/\.(test|d)\.ts$|\.d\.json\.ts$/.test(path) &&
    !ADMIN_ONLY_SOURCES.includes(at(path))
  )
    sourceFiles.push(path);
};
for (const entry of LOCALIZED_SOURCES) collect(join(ROOT, entry));
for (const path of sourceFiles)
  for (const { line, message } of scanSource(path, read(path), styleGuide.doNotTranslate))
    report(`${at(path)}:${line}`, message);

for (const problem of problems) console.error(problem);
console.log(
  `i18n: ${problems.length === 0 ? "no problems" : `${problems.length} problem(s)`} — ${LANGUAGE_CODES.length} languages, ` +
    `${englishNamespaces.length} namespace(s), ${messageCount} messages, ${sourceFiles.length} localized source files.`,
);
process.exitCode = problems.length === 0 ? 0 : 1;
