"use client";

import * as React from "react";

import { Check, Copy } from "lucide-react";
import { toast } from "sonner";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { copyText } from "@/lib/copy-text";

export function MessageAction(props: React.ComponentProps<typeof Button>) {
  return (
    <Button
      variant="ghost"
      size="xs"
      className="h-6 gap-1 px-2 font-normal text-muted-foreground text-xs hover:text-foreground [&_svg:not([class*='size-'])]:size-3.5"
      {...props}
    />
  );
}

export function CopyAction({ text }: { readonly text: string }) {
  const t = useTranslations("leo");
  const [copied, setCopied] = React.useState(false);

  React.useEffect(() => {
    if (!copied) return;
    const timeout = setTimeout(() => setCopied(false), 2000);
    return () => clearTimeout(timeout);
  }, [copied]);

  const copy = async () => {
    try {
      await copyText(text.replaceAll("**", ""));
      setCopied(true);
    } catch {
      toast.error(t("message.copyFailed"));
    }
  };

  return (
    <MessageAction onClick={copy} aria-live="polite">
      {copied ? <Check /> : <Copy />}
      {copied ? t("message.copied") : t("message.copy")}
    </MessageAction>
  );
}
