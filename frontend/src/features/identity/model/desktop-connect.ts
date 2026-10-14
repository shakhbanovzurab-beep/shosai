import { issueDesktopCode } from "../api/desktop-api";
import { type DesktopRequest, desktopReturnUrl } from "../domain/desktop-link";
import { attempt, type Outcome } from "./outcome";

/**
 * Подключить десктоп-приложение: одноразовый код под сессией браузера и возврат в приложение. Переход —
 * документа целиком: схему `shosai://` браузер открывает только по явному переходу страницы.
 */
export async function connectDesktop(request: DesktopRequest): Promise<Outcome<void>> {
  const outcome = await attempt(() => issueDesktopCode(request.codeChallenge));
  if (outcome.kind === "done") window.location.assign(desktopReturnUrl(outcome.value, request.state));
  return outcome.kind === "done" ? { kind: "done", value: undefined } : outcome;
}
