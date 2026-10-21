import { toast } from "sonner";

/*
 * Удаление с Undo, как в Files и Notes: показать результат сразу, отправить, когда тост закроется без Undo,
 * вернуть всё на место по Undo.
 */

type UndoableChange = {
  message: string;
  undoLabel: string;
  /** Убрать с экрана сейчас. */
  hide: () => void;
  /** Вернуть, если человек нажал Undo. */
  restore: () => void;
  /** Отправить на сервер; сбой возвращает на место сам. */
  commit: () => Promise<unknown>;
};

export function withUndo({ message, undoLabel, hide, restore, commit }: UndoableChange) {
  let settled = false;
  const finish = () => {
    if (settled) return;
    settled = true;
    void commit();
  };
  hide();
  toast(message, {
    action: {
      label: undoLabel,
      onClick: () => {
        settled = true;
        restore();
      },
    },
    onAutoClose: finish,
    onDismiss: finish,
  });
}
