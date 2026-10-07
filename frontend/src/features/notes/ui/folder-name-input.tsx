"use client";

import * as React from "react";

import { useTranslations } from "next-intl";

interface FolderNameInputProps {
  readonly initialName: string;
  readonly onSubmit: (name: string) => void;
  readonly onCancel: () => void;
}

export function FolderNameInput({ initialName, onSubmit, onCancel }: FolderNameInputProps) {
  const t = useTranslations("notes");
  const [name, setName] = React.useState(initialName);
  const inputRef = React.useRef<HTMLInputElement>(null);

  // Renaming starts from an explicit action, so focus the field with the name selected.
  React.useEffect(() => {
    inputRef.current?.select();
    inputRef.current?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, []);

  const commit = () => {
    const trimmed = name.trim();
    if (trimmed) onSubmit(trimmed);
    else onCancel();
  };

  return (
    <input
      ref={inputRef}
      value={name}
      onChange={(event) => setName(event.target.value)}
      onBlur={commit}
      onKeyDown={(event) => {
        // Enter that confirms an IME candidate (Japanese, Chinese, Korean) isn't a submit.
        if (event.key === "Enter" && !event.nativeEvent.isComposing) commit();
        if (event.key === "Escape") onCancel();
      }}
      maxLength={40}
      size={Math.max(name.length, 6)}
      aria-label={t("folders.nameLabel")}
      dir="auto"
      className="min-w-0 bg-transparent outline-none"
    />
  );
}
