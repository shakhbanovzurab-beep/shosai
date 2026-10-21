"use client";

import { SlidersHorizontal } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { useDirection } from "@/components/ui/direction";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { lazyComponent } from "@/lib/lazy-component";

// Настройки полей открывают редко: их код — отдельный кусок, который грузится при открытии листа.
const FieldsBody = lazyComponent(() => import("./fields-body").then((module) => module.FieldsBody), {
  loading: () => <Skeleton className="h-64 w-full" />,
});

/** Кнопка «Поля» панели доски и лист настроек полей. */
export function FieldsButton() {
  const t = useTranslations("kanbanFields");
  // С конца строки, как панель задачи: справа, а в арабском слева.
  const side = useDirection() === "rtl" ? "left" : "right";
  return (
    <Sheet>
      <SheetTrigger asChild>
        <Button variant="outline" className="w-full sm:w-auto">
          <SlidersHorizontal data-icon="inline-start" />
          {t("open")}
        </Button>
      </SheetTrigger>
      <SheetContent
        side={side}
        className="w-full gap-0 overflow-y-auto overscroll-contain p-5 data-[side=left]:w-full data-[side=right]:w-full sm:p-6 data-[side=left]:sm:max-w-xl data-[side=right]:sm:max-w-xl"
      >
        <SheetHeader className="mb-4 p-0 pe-8">
          <SheetTitle>{t("title")}</SheetTitle>
          <SheetDescription>{t("description")}</SheetDescription>
        </SheetHeader>
        <FieldsBody />
      </SheetContent>
    </Sheet>
  );
}
