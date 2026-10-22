import type { ReactNode } from "react";

/*
 * Шаг окна подключения сменился — нажатая кнопка ушла вместе с прежним шагом, и фокус упал бы на само окно.
 * Новый шаг отдаёт фокус своему первому элементу управления. Колбэк рефа — на уровне модуля: он стабилен и
 * срабатывает один раз, когда шаг появляется (ключ шага пересоздаёт обёртку).
 */

const CONTROL = "input:not([disabled]), button:not([disabled]), textarea, a[href], [tabindex]:not([tabindex='-1'])";

const focusFirstControl = (node: HTMLDivElement | null) => {
  node?.querySelector<HTMLElement>(CONTROL)?.focus({ preventScroll: true });
};

export function StepFocus({ children }: { children: ReactNode }) {
  return (
    <div ref={focusFirstControl} className="contents">
      {children}
    </div>
  );
}
