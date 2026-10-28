import { useState } from "react";

import { SmilePlus } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

import { REACTION_NAMES, REACTIONS } from "../../domain/reactions";

/** Шесть реакций; больше десяти за десять секунд не уходит — кнопки на миг гаснут. */
export function ReactionPicker({ onReact }: { onReact: (emoji: string) => boolean }) {
  const t = useTranslations("meetingRoom");
  const [limited, setLimited] = useState(false);
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="outline" size="icon" aria-label={t("controls.react")}>
          <SmilePlus aria-hidden="true" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-auto p-1.5" side="top">
        <fieldset className="flex gap-1">
          <legend className="sr-only">{t("controls.react")}</legend>
          {REACTIONS.map((emoji) => (
            <Button
              key={emoji}
              variant="ghost"
              size="icon"
              className="text-xl"
              disabled={limited}
              aria-label={t(`reactions.${REACTION_NAMES[emoji]}`)}
              onClick={() => {
                if (onReact(emoji)) return;
                setLimited(true);
                window.setTimeout(() => setLimited(false), 2_000);
              }}
            >
              {emoji}
            </Button>
          ))}
        </fieldset>
        {limited ? <p className="px-1.5 pt-1 text-muted-foreground text-xs">{t("reactions.limited")}</p> : null}
      </PopoverContent>
    </Popover>
  );
}
