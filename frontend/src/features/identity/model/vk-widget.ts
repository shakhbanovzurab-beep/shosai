import { startVkWidget } from "../api/social-api";
import type { WidgetTheme } from "./brand-widgets";

/** Что OneTap отдаёт странице, когда человек разрешил вход: сервер меняет это на сессию. */
export interface VkCode {
  code: string;
  state: string;
  deviceId: string;
}

interface VkOneTapLook {
  theme: WidgetTheme;
  language: string;
  next: string;
}

interface VkOneTapEvents {
  onShown: () => void;
  onCode: (answer: VkCode) => void;
  onFailed: () => void;
}

interface LoginSuccess {
  code?: unknown;
  state?: unknown;
  device_id?: unknown;
}

// Языки, которые понимает VK ID (перечисление Languages SDK); остальным — английский.
const VK_LANGUAGES: Record<string, number> = {
  ru: 0,
  uk: 1,
  en: 3,
  es: 4,
  de: 6,
  pl: 15,
  fr: 16,
  tr: 82,
  kk: 97,
  be: 114,
};
const VK_ENGLISH = 3;

/**
 * Кнопка VK ID OneTap в `container`. Поток начинает сервер (`widget-start`): verifier PKCE остаётся у него, виджет
 * получает state и хеш. SDK грузится отдельным чанком только здесь — на экране, где есть кнопка VK. Возвращает
 * функцию, закрывающую виджет; отказ — SDK не загрузился или сервер не открыл поток.
 */
export async function mountVkOneTap(
  container: HTMLElement,
  appId: number,
  look: VkOneTapLook,
  events: VkOneTapEvents,
): Promise<() => void> {
  const [vkid, flow] = await Promise.all([import("@vkid/sdk"), startVkWidget(look.next, look.language)]);
  vkid.Config.init({
    app: appId,
    redirectUrl: flow.redirect_url,
    state: flow.state,
    codeChallenge: flow.code_challenge,
    scope: "email",
    responseMode: vkid.ConfigResponseMode.Callback,
  });
  const oneTap = new vkid.OneTap()
    .render({
      container,
      scheme: look.theme === "dark" ? vkid.Scheme.DARK : vkid.Scheme.LIGHT,
      lang: VK_LANGUAGES[look.language] ?? VK_ENGLISH,
      styles: { height: 44, borderRadius: 8 },
      showAlternativeLogin: false,
    })
    .on(vkid.WidgetEvents.LOAD, events.onShown)
    .on(vkid.WidgetEvents.ERROR, events.onFailed)
    .on(vkid.OneTapInternalEvents.LOGIN_SUCCESS, (payload: LoginSuccess) => {
      const { code, state, device_id: deviceId } = payload;
      if (typeof code === "string" && typeof state === "string" && typeof deviceId === "string") {
        events.onCode({ code, state, deviceId });
      } else {
        events.onFailed();
      }
    });
  return () => oneTap.close();
}
