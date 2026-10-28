import type { ExcalidrawImperativeAPI } from "@excalidraw/excalidraw/types";
import { type LucideIcon, Workflow } from "lucide-react";

/*
 * Инструменты доски над редактором (MR-D13): у каждого id, значок, подпись и действие над сценой редактора.
 * Первый — собственный диалог Excalidraw «Mermaid → схема»; панели формул нет, но контракт инструмента сохранён.
 */

export type BoardTool = {
  id: string;
  icon: LucideIcon;
  labelKey: "board.tools.mermaid";
  open(editor: ExcalidrawImperativeAPI): void;
};

export const BOARD_TOOLS: readonly BoardTool[] = [
  {
    id: "mermaid",
    icon: Workflow,
    labelKey: "board.tools.mermaid",
    open: (editor) => editor.updateScene({ appState: { openDialog: { name: "ttd", tab: "mermaid" } } }),
  },
];
