import "@excalidraw/excalidraw/index.css";

import { useEffect, useRef, useState } from "react";

import { CaptureUpdateAction, Excalidraw, getSceneVersion, reconcileElements } from "@excalidraw/excalidraw";
import type { RemoteExcalidrawElement } from "@excalidraw/excalidraw/data/reconcile";
import type { OrderedExcalidrawElement } from "@excalidraw/excalidraw/element/types";
import type {
  AppState,
  BinaryFileData,
  BinaryFiles,
  Collaborator,
  ExcalidrawImperativeAPI,
  SocketId,
} from "@excalidraw/excalidraw/types";

import { usePreferencesStore } from "@/features/preferences/model/preferences-provider";
import { useUiLanguage } from "@/hooks/use-ui-language";

import type { BoardScene, BoardSession } from "../../domain/board";
import { boardLanguage } from "../../domain/board-languages";
import { useBoardState } from "../../model/board-state";
import { BoardTools } from "./board-tools";

/*
 * Холст доски — отдельный чанк страницы комнаты: Excalidraw грузится, только когда доску открыли. Сцена сервера и
 * правки соседей сливаются `reconcileElements` с тем, что уже на холсте; всякая новая сцена уходит в сессию доски,
 * которая решает, что разослать и что сохранить. Курсоры других — коллабораторы редактора.
 */

const elementsOf = (scene: BoardScene) => scene.elements as readonly OrderedExcalidrawElement[];

// Сцена из сети: для слияния её элементы «удалённые» (бренд типа Excalidraw), картинки добавляются к холсту.
function merge(api: ExcalidrawImperativeAPI, scene: BoardScene) {
  const files = Object.values(scene.files as BinaryFiles) as BinaryFileData[];
  if (files.length > 0) api.addFiles(files);
  const remote = elementsOf(scene) as readonly RemoteExcalidrawElement[];
  const merged = reconcileElements(api.getSceneElementsIncludingDeleted(), remote, api.getAppState());
  // Чужая правка не попадает в стек отмены: Ctrl+Z откатывает свою работу, а не соседа.
  api.updateScene({ elements: merged, captureUpdate: CaptureUpdateAction.NEVER });
}

export default function BoardCanvas({ board }: { board: BoardSession }) {
  const [api, setApi] = useState<ExcalidrawImperativeAPI | null>(null);
  const { readOnly, cursors, streams } = useBoardState(board);
  const language = useUiLanguage();
  const theme = usePreferencesStore((state) => state.resolvedThemeMode);
  const container = useRef<HTMLDivElement>(null);
  // Версия сцены, которую доска уже знает: курсоры и выбор на холсте сцену не меняют и не рассылаются.
  const known = useRef(-1);

  useEffect(() => {
    if (!api) return;
    let live = true;
    void board.load().then((scene) => {
      if (live) merge(api, scene);
    });
    const stop = board.onRemote((scene) => merge(api, scene));
    return () => {
      live = false;
      stop();
      void board.close();
    };
  }, [api, board]);

  useEffect(() => {
    if (!api) return;
    const collaborators = new Map<SocketId, Collaborator>(
      cursors.map((cursor) => [
        cursor.identity as SocketId,
        { username: cursor.name, pointer: { x: cursor.x, y: cursor.y, tool: "pointer" } },
      ]),
    );
    api.updateScene({ collaborators });
  }, [api, cursors]);

  useEffect(() => {
    if (!api || !streams || !container.current) return;
    return board.stream(container.current);
  }, [api, board, streams]);

  function changed(elements: readonly OrderedExcalidrawElement[], _state: AppState, files: BinaryFiles) {
    const version = getSceneVersion(elements);
    if (version === known.current) return;
    known.current = version;
    board.change({ elements, files });
  }

  return (
    <div ref={container} className="size-full">
      <Excalidraw
        excalidrawAPI={setApi}
        langCode={boardLanguage(language)}
        theme={theme}
        viewModeEnabled={readOnly}
        isCollaborating
        onChange={changed}
        onPointerUpdate={({ pointer }) => board.pointer(pointer.x, pointer.y)}
        renderTopRightUI={() => (readOnly ? null : <BoardTools editor={api} />)}
        UIOptions={{ canvasActions: { loadScene: false, saveToActiveFile: false, export: false } }}
      />
    </div>
  );
}
