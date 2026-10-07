import Link from "next/link";

import { Lock } from "lucide-react";
import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("pages");
  return {
    title: t("unauthorized.metaTitle"),
    robots: {
      index: false,
      follow: false,
    },
  };
}

export default async function page() {
  const t = await getTranslations("pages");
  return (
    <div className="flex min-h-dvh flex-col items-center justify-center bg-background px-4 py-12 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-md text-center">
        <Lock className="mx-auto size-12 text-primary" aria-hidden="true" />
        <h1 className="mt-4 font-bold text-3xl tracking-tight sm:text-4xl">{t("unauthorized.title")}</h1>
        <p className="mt-4 text-muted-foreground">{t("unauthorized.description")}</p>
        <div className="mt-6">
          <Link
            href="/app"
            className="inline-flex items-center rounded-md bg-primary px-4 py-2 font-medium text-primary-foreground text-sm shadow-xs transition-colors hover:bg-primary/90 focus:outline-hidden focus:ring-2 focus:ring-primary focus:ring-offset-2"
            prefetch={false}
          >
            {t("actions.goHome")}
          </Link>
        </div>
      </div>
    </div>
  );
}
