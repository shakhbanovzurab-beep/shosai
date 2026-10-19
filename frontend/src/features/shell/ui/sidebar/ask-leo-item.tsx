"use client";

import { ThinkingOrb } from "thinking-orbs";
import { useTranslations } from "use-intl";

import { CommandGroup, CommandItem } from "@/components/ui/command";

/**
 * Последняя строка ⌘K, пока что-то набрано: набранное уходит вопросом к Leo. Видна всегда (`forceMount`), а не
 * только когда страниц не нашлось, — так у поиска нет пустого состояния: спросить Leo можно о чём угодно.
 */
export function AskLeoItem({ question, onAsk }: { question: string; onAsk: () => void }) {
  const t = useTranslations("shell");
  return (
    <CommandGroup forceMount>
      <CommandItem forceMount value={`ask-leo ${question}`} onSelect={onAsk}>
        {/* Leo везде выглядит своей сферой. */}
        <span className="flex size-4 shrink-0 [&_canvas]:size-4!" aria-hidden="true">
          <ThinkingOrb state="breathing" size={20} />
        </span>
        <span className="truncate" dir="auto">
          {t("search.askLeo", { question })}
        </span>
      </CommandItem>
    </CommandGroup>
  );
}
