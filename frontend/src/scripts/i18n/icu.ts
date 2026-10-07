import { type MessageFormatElement, parse, TYPE } from "@formatjs/icu-messageformat-parser";

/** What a message needs from the code and what each language must provide, read from its ICU syntax. */
export interface MessageShape {
  /** Every argument as `name:kind`, e.g. `count:plural`, `name:text`, `link:tag`. */
  arguments: Set<string>;
  /** The options of each `select`, by argument name. */
  selects: Map<string, string[]>;
  /** Every `plural` and `selectordinal`, with the options it writes. */
  plurals: { name: string; ordinal: boolean; options: string[] }[];
  /** The words of the message outside ICU syntax, one entry per run of text. */
  text: string[];
}

export type ReadResult = { shape: MessageShape } | { error: string };

const KIND: Partial<Record<TYPE, string>> = {
  [TYPE.argument]: "text",
  [TYPE.number]: "number",
  [TYPE.date]: "date",
  [TYPE.time]: "time",
  [TYPE.select]: "select",
  [TYPE.tag]: "tag",
};

function walk(elements: MessageFormatElement[], shape: MessageShape) {
  for (const element of elements) {
    if (element.type === TYPE.literal) {
      shape.text.push(element.value);
    } else if (element.type === TYPE.plural) {
      const ordinal = element.pluralType === "ordinal";
      shape.arguments.add(`${element.value}:${ordinal ? "selectordinal" : "plural"}`);
      shape.plurals.push({ name: element.value, ordinal, options: Object.keys(element.options) });
      for (const option of Object.values(element.options)) walk(option.value, shape);
    } else if (element.type === TYPE.select) {
      shape.arguments.add(`${element.value}:select`);
      shape.selects.set(element.value, Object.keys(element.options).sort());
      for (const option of Object.values(element.options)) walk(option.value, shape);
    } else if (element.type === TYPE.tag) {
      shape.arguments.add(`${element.value}:tag`);
      walk(element.children, shape);
    } else if (element.type !== TYPE.pound) {
      shape.arguments.add(`${element.value}:${KIND[element.type]}`);
    }
  }
}

/** Parses a message as `next-intl` will: ICU MessageFormat with rich-text tags, `other` required. */
export function readMessage(message: string): ReadResult {
  try {
    const shape: MessageShape = { arguments: new Set(), selects: new Map(), plurals: [], text: [] };
    walk(parse(message, { requiresOtherClause: true }), shape);
    return { shape };
  } catch (error) {
    return { error: error instanceof Error ? error.message : String(error) };
  }
}

const rulesCache = new Map<string, string[]>();

/** The plural categories a language distinguishes (CLDR, as the browser's Intl.PluralRules sees them). */
export function pluralCategories(language: string, ordinal: boolean): string[] {
  const key = `${language}|${ordinal}`;
  let categories = rulesCache.get(key);
  if (!categories) {
    const rules = new Intl.PluralRules(language, { type: ordinal ? "ordinal" : "cardinal" });
    categories = [...rules.resolvedOptions().pluralCategories];
    rulesCache.set(key, categories);
  }
  return categories;
}
