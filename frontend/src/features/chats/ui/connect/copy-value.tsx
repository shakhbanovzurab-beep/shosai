"use client";

import { useState } from "react";

import { cn } from "cn";
import { Check, Copy } from "lucide-react";
import { toast } from "sonner";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { copyText } from "@/lib/copy-text";

/*
 * Значение, которое человек переносит в мессенджер руками: код или команда. Показано слева направо и без
 * перевода в любом языке интерфейса, копируется одной кнопкой.
 */

export function CopyValue({
  value,
  shown,
  copyLabel,
  copied,
  size,
}: {
  value: string;
  /** Как значение выглядит на экране (код — двумя группами); копируется `value`. */
  shown: string;
  copyLabel: string;
  copied: string;
  size: "code" | "command";
}) {
  const t = useTranslations("chatsConnect");
  const [done, setDone] = useState(false);
  const copy = async () => {
    try {
      await copyText(value);
      setDone(true);
      toast.success(copied);
    } catch {
      toast.error(t("copyFailed"));
    }
  };
  return (
    <div className="flex items-center gap-2 rounded-lg border bg-muted/40 px-3 py-2">
      <span
        dir="ltr"
        translate="no"
        spellCheck={false}
        className={cn(
          "min-w-0 flex-1 select-all font-mono",
          size === "code" ? "font-semibold text-2xl tracking-widest" : "break-all text-sm",
        )}
      >
        {shown}
      </span>
      <Button type="button" variant="ghost" size="icon-sm" aria-label={copyLabel} onClick={() => void copy()}>
        {done ? <Check /> : <Copy />}
      </Button>
    </div>
  );
}
