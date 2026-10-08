"use client";

import { EmojiPicker, type EmojiPickerListCategoryHeaderProps, type EmojiPickerListEmojiProps } from "frimousse";
import { useTranslations } from "use-intl";

import { useUiLanguage } from "@/hooks/use-ui-language";
import type { LanguageCode } from "@/lib/language";

/** Emojibase locales (category names and search keywords) for the interface languages; languages it doesn't ship fall back to English. */
const EMOJI_LOCALES: Partial<Record<LanguageCode, string>> = {
  fr: "fr",
  de: "de",
  ru: "ru",
  nl: "nl",
  it: "it",
  es: "es",
  "pt-BR": "pt",
  ko: "ko",
  hi: "hi",
  vi: "vi",
  "zh-Hant": "zh-hant",
  ja: "ja",
};

function CategoryHeader({ category, ...props }: EmojiPickerListCategoryHeaderProps) {
  return (
    <div {...props} className="bg-popover px-2 pt-2 pb-1 font-medium text-muted-foreground text-xs">
      {category.label}
    </div>
  );
}

function Emoji({ emoji, ...props }: EmojiPickerListEmojiProps) {
  return (
    <button
      {...props}
      type="button"
      className="flex size-8 items-center justify-center rounded-md text-lg data-active:bg-accent"
    >
      {emoji.emoji}
    </button>
  );
}

const LIST_COMPONENTS = { CategoryHeader, Emoji };

/** The picker itself (frimousse); loaded only when the emoji popover first opens. */
export default function EmojiPickerPanel({ onSelect }: { onSelect: (emoji: string) => void }) {
  const language = useUiLanguage();
  const t = useTranslations("pages");
  const tc = useTranslations("common");
  return (
    <EmojiPicker.Root
      locale={EMOJI_LOCALES[language] ?? "en"}
      columns={8}
      onEmojiSelect={({ emoji }) => onSelect(emoji)}
      className="isolate flex h-80 w-fit flex-col bg-popover"
    >
      <EmojiPicker.Search
        placeholder={t("emoji.search")}
        aria-label={t("emoji.search")}
        className="m-2 h-8 rounded-md border bg-background px-2.5 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
      />
      <EmojiPicker.Viewport className="relative flex-1 outline-hidden">
        <EmojiPicker.Loading className="absolute inset-0 flex items-center justify-center text-muted-foreground text-sm">
          {tc("feedback.loading")}
        </EmojiPicker.Loading>
        <EmojiPicker.Empty className="absolute inset-0 flex items-center justify-center text-muted-foreground text-sm">
          {t("emoji.empty")}
        </EmojiPicker.Empty>
        <EmojiPicker.List className="select-none px-1 pb-1" components={LIST_COMPONENTS} />
      </EmojiPicker.Viewport>
    </EmojiPicker.Root>
  );
}
