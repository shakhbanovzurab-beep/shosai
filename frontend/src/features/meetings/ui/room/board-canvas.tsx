import "@excalidraw/excalidraw/index.css";

import { useEffect, useRef, useState } from "react";

import { CaptureUpdateAction, Excalidraw, getSceneVersion, reconcileElements } from "@excalidraw/excalidraw";
import type { RemoteExcalidrawElement } from "@excalidraw/excalidraw/data/reconcile";
import type { OrderedExcalidrawElement } from "@excalidraw/excalidraw/element/types";
import type {
  AppState,
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

/*
 * Холст доски — отдельный чанк страницы комнаты: Excalidraw грузится, только когда доску открыли. Правки уходят в
 * сессию доски, чужие правки сливаются `reconcileElements`, курсоры других — его же коллабораторы.
 */

const elementsOf = (scene: BoardScene) => scene.elements as readonly OrderedExcalidrawElement[];

export default function BoardCanvas({ board }: { board: BoardSession }) {
  const [api, setApi] = useState<ExcalidrawImperativeAPI | null>(null);
  const { readOnly, cursors } = useBoardState(board);
  const language = useUiLanguage();
  const theme = usePreferencesStore((state) => state.resolvedThemeMode);
  // Версия сцены, которую доска уже знает: обновления курсоров и своих же правок не сохраняются заново.
  const known = useRef(-1);

  useEffect(() => {
    if (!api) return;
    let live = true;
    void board.load().then((scene) => {
      if (!live) return;
      known.current = getSceneVersion(elementsOf(scene));
      api.updateScene({ elements: elementsOf(scene), captureUpdate: CaptureUpdateAction.NEVER });
    });
    const stop = board.onRemote((scene) => {
      const local = api.getSceneElementsIncludingDeleted();
      // Чужая сцена пришла из сети: для слияния она «удалённая» (бренд типа Excalidraw).
      const remote = elementsOf(scene) as readonly RemoteExcalidrawElement[];
      const merged = reconcileElements(local, remote, api.getAppState());
      known.current = getSceneVersion(merged);
      api.updateScene({ elements: merged, captureUpdate: CaptureUpdateAction.NEVER });
    });
    return () => {
      live = false;
      stop();
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

  function changed(elements: readonly OrderedExcalidrawElement[], _state: AppState, files: BinaryFiles) {
    const version = getSceneVersion(elements);
    if (version === known.current) return;
    known.current = version;
    board.change({ elements, files });
  }

  return (
    <div className="size-full">
      <Excalidraw
        excalidrawAPI={setApi}
        langCode={boardLanguage(language)}
        theme={theme}
        viewModeEnabled={readOnly}
        isCollaborating
        onChange={changed}
        onPointerUpdate={({ pointer }) => board.pointer(pointer.x, pointer.y)}
        UIOptions={{ canvasActions: { loadScene: false, saveToActiveFile: false, export: false } }}
      />
    </div>
  );
}
