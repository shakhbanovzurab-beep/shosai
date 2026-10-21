"use client";

import { Plus } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";

import { useBoardCommands } from "./board-store";

/** «Добавить колонку» после последней колонки доски. */
export function AddColumnButton({ position }: { position: number }) {
  const { askNewColumn } = useBoardCommands();
  const t = useTranslations("kanban");
  return (
    <div className="max-sm:snap-start">
      <Button
        variant="ghost"
        className="w-full justify-start text-muted-foreground"
        onClick={() => askNewColumn(position)}
      >
        <Plus data-icon="inline-start" />
        {t("column.add")}
      </Button>
    </div>
  );
}
