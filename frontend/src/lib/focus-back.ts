import type { RefObject } from "react";

/**
 * Для `onCloseAutoFocus` окна, которое открыл не его Trigger (кнопка рядом, пункт меню, выбор в списке): Radix
 * вернул бы фокус только своему Trigger, а без него фокус падает в body. Фокус получает элемент из `opener`,
 * если он ещё на странице; иначе решает Radix. Вызывается из обработчика, а не при рендере: ref читается в момент
 * закрытия.
 */
export function focusBack(event: Event, opener: RefObject<HTMLElement | null>) {
  const element = opener.current;
  if (!element?.isConnected) return;
  event.preventDefault();
  element.focus();
}
