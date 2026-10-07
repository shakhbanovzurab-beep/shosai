import type { ReactNode } from "react";

import type { Metadata } from "next";
import { getLocale, getTranslations } from "next-intl/server";

import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { APP_CONFIG } from "@/config/app-config";
import { SITE_URL } from "@/config/site-url";
import { fontVars, PREFERENCE_DEFAULTS, PreferencesStoreProvider, ThemeBootScript } from "@/features/preferences";
import { I18nProvider } from "@/i18n/i18n-provider";
import { languageDirection } from "@/lib/language";

import "./globals.css";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("pages");
  return {
    metadataBase: SITE_URL,
    title: APP_CONFIG.meta.title,
    description: t("meta.description"),
    twitter: {
      card: "summary_large_image",
    },
  };
}

export default async function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  const { theme_mode, theme_preset, content_layout, navbar_style, sidebar_variant, sidebar_collapsible, font } =
    PREFERENCE_DEFAULTS;
  // The language comes from the request (the user's choice, or Russian for the admin panel), so the very
  // first HTML is already in it and written in its direction: nothing switches after load.
  const locale = await getLocale();
  const dir = languageDirection(locale);
  return (
    <html
      lang={locale}
      dir={dir}
      data-theme-mode={theme_mode}
      data-theme-preset={theme_preset}
      data-content-layout={content_layout}
      data-navbar-style={navbar_style}
      data-sidebar-variant={sidebar_variant}
      data-sidebar-collapsible={sidebar_collapsible}
      data-font={font}
      suppressHydrationWarning
    >
      <head>
        {/* Applies theme and layout preferences on load to avoid flicker and unnecessary server rerenders. */}
        <ThemeBootScript />
      </head>
      <body className={`${fontVars} min-h-screen antialiased`}>
        <I18nProvider dir={dir}>
          <TooltipProvider>
            <PreferencesStoreProvider initialValues={PREFERENCE_DEFAULTS}>
              {children}
              <Toaster dir={dir} />
            </PreferencesStoreProvider>
          </TooltipProvider>
        </I18nProvider>
      </body>
    </html>
  );
}
