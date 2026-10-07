"use client";

import { useRouter } from "next/navigation";

import { ArrowLeft } from "lucide-react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";

/** Steps back in history; opened straight from a link (no history), it goes home instead. */
export function GoBackButton({ fallbackHref }: { fallbackHref: string }) {
  const t = useTranslations("pages");
  const router = useRouter();
  return (
    <Button
      variant="outline"
      size="lg"
      onClick={() => (window.history.length > 1 ? router.back() : router.push(fallbackHref))}
    >
      <ArrowLeft data-icon="inline-start" className="rtl:-scale-x-100" />
      {t("actions.goBack")}
    </Button>
  );
}
