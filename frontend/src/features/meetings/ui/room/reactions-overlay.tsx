import type { CallPerson } from "../../domain/call";
import type { ShownReaction } from "../../domain/reactions";

/** Реакции всплывают у края сцены на четыре секунды; экранным чтецам их не зачитывают — это шум. */
export function ReactionsOverlay({ reactions, people }: { reactions: ShownReaction[]; people: CallPerson[] }) {
  if (reactions.length === 0) return null;
  const nameOf = (identity: string) => people.find((person) => person.identity === identity)?.name ?? "";
  return (
    <ul
      aria-hidden="true"
      className="pointer-events-none absolute start-4 bottom-20 flex max-h-[60%] flex-col-reverse gap-1 overflow-hidden"
    >
      {reactions.toReversed().map((reaction) => (
        <li
          key={reaction.id}
          className="fade-in slide-in-from-bottom-4 flex animate-in items-center gap-1.5 rounded-full bg-background/90 px-2.5 py-1 shadow-sm duration-300 motion-reduce:animate-none"
        >
          <span className="text-xl leading-none">{reaction.emoji}</span>
          <span dir="auto" className="max-w-32 truncate text-xs">
            {nameOf(reaction.from)}
          </span>
        </li>
      ))}
    </ul>
  );
}
