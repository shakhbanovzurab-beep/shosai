"use client";

import { useState } from "react";

import { Layers } from "lucide-react";
import { useFormatter, useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

import { useBoardStickers } from "../../model/board-hooks";
import { useOwnedStickers } from "../../model/stickers-resource";

/** «С других досок»: свои поля человека, которых нет на этой доске, с досками, где они стоят. */
export function OtherBoardsPicker({ disabled, onPick }: { disabled: boolean; onPick: (stickerId: string) => void }) {
  const t = useTranslations("kanbanFields");
  const tc = useTranslations("common");
  const format = useFormatter();
  const [open, setOpen] = useState(false);
  const here = new Set(useBoardStickers().map((sticker) => sticker.id));
  const owned = useOwnedStickers();
  const others = owned.status === "ready" ? owned.data.items.filter((sticker) => !here.has(sticker.id)) : [];
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm" disabled={disabled}>
          <Layers data-icon="inline-start" />
          {t("fromOther")}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80 p-0">
        <Command>
          <CommandInput placeholder={t("fromOtherSearch")} />
          <CommandList>
            <CommandEmpty>
              {owned.status === "loading" ? tc("feedback.loading") : null}
              {owned.status === "error" ? t("fromOtherFailed") : null}
              {owned.status === "ready" ? t("fromOtherEmpty") : null}
            </CommandEmpty>
            <CommandGroup>
              {others.map((sticker) => (
                <CommandItem
                  key={sticker.id}
                  value={`${sticker.name} ${sticker.id}`}
                  onSelect={() => {
                    setOpen(false);
                    onPick(sticker.id);
                  }}
                  className="flex-col items-start gap-0.5"
                >
                  <span dir="auto" className="font-medium">
                    {sticker.name}
                  </span>
                  <span className="text-muted-foreground text-xs">
                    {t(`kinds.${sticker.kind}`)} ·{" "}
                    {sticker.boards.length > 0
                      ? t("onBoards", {
                          boards: format.list(
                            sticker.boards.map((board) => board.name),
                            { type: "conjunction" },
                          ),
                        })
                      : t("onNoBoard")}
                  </span>
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
