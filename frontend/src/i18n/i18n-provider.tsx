import type { ReactNode } from "react";

import { NextIntlClientProvider } from "next-intl";

import { DirectionProvider } from "@/components/ui/direction";
import type { TextDirection } from "@/lib/language";

/**
 * The request's language for Client Components (messages, formats, time zone) and its text direction for
 * Radix primitives. Rendered once, by the root layout, next to the `<html lang dir>` it sets.
 */
export function I18nProvider({ dir, children }: Readonly<{ dir: TextDirection; children: ReactNode }>) {
  return (
    <NextIntlClientProvider>
      <DirectionProvider dir={dir}>{children}</DirectionProvider>
    </NextIntlClientProvider>
  );
}
