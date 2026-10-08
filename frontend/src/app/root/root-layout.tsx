import { useState } from "react";

import { QueryClientProvider } from "@tanstack/react-query";
import { Outlet, ScrollRestoration, useLoaderData } from "react-router";

import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { PREFERENCE_DEFAULTS } from "@/features/preferences/domain/registry";
import { PreferencesStoreProvider, usePreferencesStore } from "@/features/preferences/model/preferences-provider";
import { I18nProvider } from "@/i18n/i18n-provider";
import { createQueryClient } from "@/lib/api/query-client";
import { languageDirection } from "@/lib/language";

import type { RootData } from "./root-loader";

// Тосты следуют теме интерфейса из настроек.
function ThemedToaster({ dir }: { dir: "ltr" | "rtl" }) {
  const theme = usePreferencesStore((state) => state.values.theme_mode);
  return <Toaster dir={dir} theme={theme} />;
}

/** Провайдеры всех страниц: язык, серверное состояние, подсказки, настройки и тосты. */
export function RootLayout() {
  const { locale } = useLoaderData<RootData>();
  const [queryClient] = useState(createQueryClient);
  const dir = languageDirection(locale);
  return (
    <I18nProvider locale={locale}>
      <QueryClientProvider client={queryClient}>
        <TooltipProvider>
          <PreferencesStoreProvider initialValues={PREFERENCE_DEFAULTS}>
            <Outlet />
            <ThemedToaster dir={dir} />
          </PreferencesStoreProvider>
        </TooltipProvider>
      </QueryClientProvider>
      <ScrollRestoration />
    </I18nProvider>
  );
}
