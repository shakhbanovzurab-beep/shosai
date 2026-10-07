"use client";

import { type ReactElement, useState } from "react";

import dynamic from "next/dynamic";

import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Skeleton } from "@/components/ui/skeleton";

const EmojiPickerPanel = dynamic(() => import("./emoji-picker-panel"), {
  ssr: false,
  loading: () => <Skeleton className="h-80 w-[17rem]" />,
});

type EmojiButtonProps = {
  onSelect: (emoji: string) => void;
  /** The trigger element, e.g. a Button or InputGroupButton; it receives the popover's trigger props. */
  children: ReactElement;
};

/** A smiley button that opens an emoji picker; the popover stays open so several emoji can be added in a row. */
export function EmojiButton({ onSelect, children }: EmojiButtonProps) {
  const [open, setOpen] = useState(false);
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>{children}</PopoverTrigger>
      <PopoverContent align="end" className="w-fit p-0">
        {open ? <EmojiPickerPanel onSelect={onSelect} /> : null}
      </PopoverContent>
    </Popover>
  );
}
