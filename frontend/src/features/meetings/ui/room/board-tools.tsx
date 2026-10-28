import type { ExcalidrawImperativeAPI } from "@excalidraw/excalidraw/types";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";

import { BOARD_TOOLS } from "./board-tool-registry";

/** Кнопки инструментов в верхней панели редактора; на доске только для чтения их нет. */
export function BoardTools({ editor }: { editor: ExcalidrawImperativeAPI | null }) {
  const t = useTranslations("meetingRoom");
  if (!editor) return null;
  return (
    <div className="flex gap-1">
      {BOARD_TOOLS.map((tool) => (
        <Button key={tool.id} variant="outline" size="sm" onClick={() => tool.open(editor)}>
          <tool.icon data-icon="inline-start" />
          {t(tool.labelKey)}
        </Button>
      ))}
    </div>
  );
}
