import { loadSdk } from "../api/sdk-script";

// Фирменные кнопки входа рисуют сами сервисы, в своих iframe: подделка их кнопки выглядела бы подделкой.
const YANDEX_SDK = "https://yastatic.net/s3/passport-sdk/autofill/v1/sdk-suggest-with-polyfills-latest.js";
const GOOGLE_SDK = "https://accounts.google.com/gsi/client";
// Страница бэкенда, на которую Яндекс возвращает токен; её адрес зарегистрирован в приложении Яндекс ID.
const YANDEX_TOKEN_PAGE = "/v1/auth/social/yandex/token-page";

export type WidgetTheme = "light" | "dark";

interface YandexSuggest {
  init(
    oauth: { client_id: string; response_type: "token"; redirect_uri: string },
    tokenPageOrigin: string,
    suggest: Record<string, string | number>,
  ): Promise<{ status: string; handler?: () => Promise<{ access_token?: string }>; code?: string }>;
}

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
 * Кнопка «Войти с Яндекс ID» SDK Яндекса в элементе с `containerId`; промис отдаёт токен, когда человек
 * разрешил вход. Отказ — SDK не загрузился или человек закрыл окно.
 */
export async function mountYandexButton(
  containerId: string,
  clientId: string,
  look: { theme: WidgetTheme; russian: boolean },
): Promise<string> {
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
  const answer = await widget.handler();
  if (!answer.access_token) throw new Error("Yandex ID answered no token");
  return answer.access_token;
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
    theme: look.theme === "dark" ? "filled_black" : "outline",
    size: "large",
    text: "continue_with",
    shape: "rectangular",
    logo_alignment: "left",
    locale: look.locale,
    width: Math.min(400, Math.round(look.width)),
  });
}
