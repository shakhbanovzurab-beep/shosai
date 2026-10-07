"use client";

import { Copy } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { copyText } from "@/lib/copy-text";

/** A shortened checksum with a button that copies the whole value. */
export function Sha256Text({ value }: { value: string }) {
  const copy = () =>
    copyText(value).then(
      () => toast.success("SHA-256 скопирован"),
      () => toast.error("Не удалось скопировать"),
    );
  return (
    <div className="flex min-w-0 items-center gap-1 text-muted-foreground text-xs">
      <span className="shrink-0">SHA-256:</span>
      <code className="truncate font-mono" title={value} translate="no">
        {value.slice(0, 12)}…{value.slice(-8)}
      </code>
      <Button variant="ghost" size="icon-xs" onClick={() => void copy()} aria-label="Скопировать SHA-256">
        <Copy />
      </Button>
    </div>
  );
}
