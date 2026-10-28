import { nonLatinLetters } from "../domain/platform-layer";

const SHOWN = 6;

/** Предупреждает до публикации: модель читает этот текст, и он должен быть английским. */
export function NotEnglishHint({ text }: { text: string }) {
  const letters = nonLatinLetters(text);
  if (letters.length === 0) return null;
  const sample = letters.slice(0, SHOWN).join(" ");

  return (
    <p className="text-amber-700 text-xs dark:text-amber-400" role="status">
      Текст читает модель, поэтому он пишется по-английски — иначе публикация не пройдёт. Не латиница: {sample}
      {letters.length > SHOWN ? " …" : null}
    </p>
  );
}
