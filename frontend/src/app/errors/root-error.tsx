import { RotateCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { interfaceLanguage } from "@/lib/api/interface-language";

import { failureTexts } from "virtual:i18n-failure-texts";

/**
 * Сбой корня: не загрузился каталог языка или упали провайдеры. Переводов в этот момент может не быть,
 * поэтому тексты — из модуля сборки (все языки, ~2 КБ), язык — из `<html lang>`, который поставил boot-скрипт.
 */
export function RootError() {
  const text = failureTexts[interfaceLanguage()];
  return (
    <main className="flex min-h-dvh flex-col items-center justify-center bg-background px-4 py-12 text-center">
      <title>{text.title}</title>
      <h1 className="font-semibold text-2xl tracking-tight sm:text-3xl">{text.title}</h1>
      <p className="mt-3 max-w-md text-balance text-muted-foreground">{text.description}</p>
      <Button size="lg" className="mt-8" onClick={() => window.location.reload()}>
        <RotateCw data-icon="inline-start" />
        {text.reload}
      </Button>
    </main>
  );
}
