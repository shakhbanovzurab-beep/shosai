import { loadSdk } from "../api/sdk-script";

// Фирменные кнопки входа рисуют сами сервисы, в своих iframe: подделка их кнопки выглядела бы подделкой.
const YANDEX_SDK = "https://yastatic.net/s3/passport-sdk/autofill/v1/sdk-suggest-with-polyfills-latest.js";
const GOOGLE_SDK = "https://accounts.google.com/gsi/client";
// Страница бэкенда, на которую Яндекс возвращает токен; её адрес зарегистрирован в приложении Яндекс ID.
const YANDEX_TOKEN_PAGE = "/v1/auth/social/yandex/token-page";

export type WidgetTheme = "light" | "dark";

// Заливка тёмной кнопки Google Identity (filled_black): ею же в тёмной теме закрашены рамка вокруг кнопки и
// запасная ссылка.
export const GOOGLE_BUTTON_FILL = "#202124";

type YandexTokenHandler = () => Promise<{ access_token?: string }>;

interface YandexSuggest {
  init(
    oauth: { client_id: string; response_type: "token"; redirect_uri: string },
    tokenPageOrigin: string,
    suggest: Record<string, string | number>,
  ): Promise<{ status: string; handler?: YandexTokenHandler; code?: string }>;
}

/**
 * SDK Яндекса не поставил кнопку: не загрузился скрипт, `init` отказал или ответил ошибкой. Так бывает через VPN:
 * загрузчик SDK ждёт ответа `autofill.yandex.ru` не дольше 5 с и после этого до перезагрузки страницы отказывает
 * в каждом `init` — повторять бесполезно, на месте кнопки остаётся ссылка входа.
 */
export class YandexIdUnavailableError extends Error {}

interface GoogleIdentity {
  initialize(config: {
    client_id: string;
    callback: (answer: { credential?: string }) => void;
    ux_mode: "popup";
  }): void;
  renderButton(parent: HTMLElement, options: Record<string, string | number>): void;
}

type BrandWindow = Window & { YaAuthSuggest?: YandexSuggest; google?: { accounts: { id: GoogleIdentity } } };

/**
 * SDK Яндекса заранее: на русском экране входа кнопка Яндекса будет почти наверняка, а цепочка загрузок SDK
 * длинная (скрипт, версия, клиент, фрейм кнопки), — начинать её стоит до ответа со списком провайдеров.
 * Неудача здесь ничего не ломает: кнопка повторит загрузку сама и при отказе покажет обычную ссылку входа.
 */
export function preloadYandexSdk(): void {
  loadSdk(YANDEX_SDK).catch(() => undefined);
}

/**
 * Кнопка «Войти с Яндекс ID» SDK Яндекса в элементе с `containerId`; `onShown` — когда SDK её нарисовал,
 * промис отдаёт токен, когда человек разрешил вход. Отказ `YandexIdUnavailableError` — кнопки не будет; любой
 * другой — окно Яндекса закрылось без токена, и SDK убрал свой фрейм.
 */
export async function mountYandexButton(
  containerId: string,
  clientId: string,
  look: { theme: WidgetTheme; russian: boolean },
  onShown: () => void,
): Promise<string> {
  let waitForToken: YandexTokenHandler;
  try {
    waitForToken = await startYandexButton(containerId, clientId, look);
  } catch (error) {
    throw new YandexIdUnavailableError("Yandex ID button did not start", { cause: error });
  }
  onShown();
  const answer = await waitForToken();
  if (!answer.access_token) throw new Error("Yandex ID answered no token");
  return answer.access_token;
}

async function startYandexButton(
  containerId: string,
  clientId: string,
  look: { theme: WidgetTheme; russian: boolean },
): Promise<YandexTokenHandler> {
  await loadSdk(YANDEX_SDK);
  const sdk = (window as BrandWindow).YaAuthSuggest;
  if (sdk === undefined) throw new Error("Yandex ID SDK is missing after load");
  const origin = window.location.origin;
  const widget = await sdk.init(
    { client_id: clientId, response_type: "token", redirect_uri: `${origin}${YANDEX_TOKEN_PAGE}` },
    origin,
    {
      view: "button",
      parentId: containerId,
      buttonView: "main",
      buttonTheme: look.theme,
      buttonSize: "m",
      buttonBorderRadius: 8,
      buttonIcon: look.russian ? "ya" : "yaEng",
    },
  );
  if (widget.status !== "ok" || widget.handler === undefined) throw new Error(`Yandex ID: ${widget.code ?? "error"}`);
  return widget.handler.bind(widget);
}

/** Кнопка Google Identity Services; `onCredential` получает ID-токен, когда человек выбрал аккаунт. */
export async function mountGoogleButton(
  element: HTMLElement,
  clientId: string,
  look: { theme: WidgetTheme; locale: string; width: number },
  onCredential: (token: string) => void,
): Promise<void> {
  await loadSdk(GOOGLE_SDK);
  const identity = (window as BrandWindow).google?.accounts.id;
  if (identity === undefined) throw new Error("Google Identity Services are missing after load");
  identity.initialize({
    client_id: clientId,
    ux_mode: "popup",
    callback: ({ credential }) => {
      if (credential) onCredential(credential);
    },
  });
  identity.renderButton(element, {
    type: "standard",
    // Светлая кнопка в светлой теме, тёмная — в тёмной; высоту 44 px добирает рамка вокруг (GoogleButton).
    theme: look.theme === "dark" ? "filled_black" : "outline",
    size: "large",
    text: "continue_with",
    shape: "rectangular",
    logo_alignment: "left",
    locale: look.locale,
    width: Math.min(400, Math.round(look.width)),
  });
}

/**
 * Позвать `onShown`, когда кнопка Google в `element` готова: её фрейм получил размер. До этого Google показывает
 * временную HTML-кнопку на своём языке и со своим текстом, поэтому кабинет держит на её месте свою. Возвращает
 * отписку.
 */
export function watchGoogleFrame(element: HTMLElement, onShown: () => void): () => void {
  const sized = new ResizeObserver((entries) => {
    if (entries.some((entry) => entry.contentRect.width > 0)) {
      stop();
      onShown();
    }
  });
  const added = new MutationObserver(() => {
    const frame = element.querySelector("iframe");
    if (frame !== null) {
      added.disconnect();
      sized.observe(frame);
    }
  });
  const stop = () => {
    added.disconnect();
    sized.disconnect();
  };
  added.observe(element, { childList: true, subtree: true });
  return stop;
}
