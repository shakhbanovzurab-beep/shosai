import { blocksOf, lexed, type MdBlock } from "./markdown";

/*
 * Разбор ответа, пока он пишется (ADR 0068 AG-D6): готовые блоки не разбираются заново. С новым куском текста
 * лексер проходит только последний блок и то, что дописано за ним, — блоки до него те же объекты, и их разметка
 * не перерисовывается. Ответ в 5 000 слов на каждом кадре стоит одного абзаца, а не всего текста.
 */

export interface MdPart {
  /** Место блока в тексте ответа: его ключ, неизменный, пока ответ дописывается. */
  readonly key: number;
  /** Исходный текст блока, как его отдал лексер. */
  readonly raw: string;
  readonly blocks: readonly MdBlock[];
}

export interface MdDocument {
  readonly text: string;
  readonly parts: readonly MdPart[];
}

function partsOf(text: string, offset = 0): MdPart[] {
  let at = offset;
  return lexed(text).map((token) => {
    const part = { key: at, raw: token.raw, blocks: blocksOf([token]) };
    at += token.raw.length;
    return part;
  });
}

/** Документ текста; `previous` — документ его начала, чьи готовые блоки переиспользуются. */
export function parsed(text: string, previous: MdDocument | null): MdDocument {
  if (previous === null || previous.parts.length === 0 || !text.startsWith(previous.text)) {
    return { text, parts: partsOf(text) };
  }
  const kept = previous.parts.slice(0, -1);
  const prefix = kept.map((part) => part.raw).join("");
  // Блоки лексера покрывают текст подряд; если нет — разбор целиком, а не сдвинутые части.
  if (!text.startsWith(prefix)) return { text, parts: partsOf(text) };
  return { text, parts: [...kept, ...partsOf(text.slice(prefix.length), prefix.length)] };
}
