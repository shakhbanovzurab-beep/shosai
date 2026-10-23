import { afterEach, describe, expect, it, vi } from "vitest";

import { loadSdk } from "../api/sdk-script";
import { mountYandexButton, YandexIdUnavailableError } from "./brand-widgets";

vi.mock("../api/sdk-script", () => ({ loadSdk: vi.fn(async () => undefined) }));

const LOOK = { theme: "light", russian: true } as const;

// Страница с подделкой SDK Яндекса: `init` отвечает так, как велит тест.
function withYandexSdk(init: () => Promise<unknown>) {
  vi.stubGlobal("window", { location: { origin: "https://shosai.test" }, YaAuthSuggest: { init } });
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.mocked(loadSdk).mockClear();
});

describe("mountYandexButton", () => {
  it("shows the button and gives the token once the person allowed sign-in", async () => {
    const onShown = vi.fn();
    withYandexSdk(async () => ({ status: "ok", handler: async () => ({ access_token: "token-1" }) }));

    await expect(mountYandexButton("yandex-id-1", "client", LOOK, onShown)).resolves.toBe("token-1");
    expect(onShown).toHaveBeenCalledOnce();
  });

  it("calls the SDK's handler on its widget", async () => {
    const widget = {
      status: "ok",
      async handler(this: unknown) {
        return { access_token: this === widget ? "bound" : undefined };
      },
    };
    withYandexSdk(async () => widget);

    await expect(mountYandexButton("yandex-id-1", "client", LOOK, vi.fn())).resolves.toBe("bound");
  });

  it("reports the button unavailable when init refuses, as the SDK does through a slow VPN", async () => {
    const onShown = vi.fn();
    withYandexSdk(() => Promise.reject({ code: "not_available" }));

    await expect(mountYandexButton("yandex-id-1", "client", LOOK, onShown)).rejects.toBeInstanceOf(
      YandexIdUnavailableError,
    );
    expect(onShown).not.toHaveBeenCalled();
  });

  it("reports the button unavailable when init answers with an error", async () => {
    withYandexSdk(async () => ({ status: "error", code: "in_progress" }));

    await expect(mountYandexButton("yandex-id-1", "client", LOOK, vi.fn())).rejects.toBeInstanceOf(
      YandexIdUnavailableError,
    );
  });

  it("reports the button unavailable when the SDK script did not load", async () => {
    withYandexSdk(async () => ({ status: "ok", handler: async () => ({ access_token: "token-1" }) }));
    vi.mocked(loadSdk).mockRejectedValueOnce(new Error("sdk timeout"));

    await expect(mountYandexButton("yandex-id-1", "client", LOOK, vi.fn())).rejects.toBeInstanceOf(
      YandexIdUnavailableError,
    );
  });

  it("tells a window closed without sign-in apart from an unavailable button", async () => {
    const onShown = vi.fn();
    withYandexSdk(async () => ({ status: "ok", handler: () => Promise.reject("close_widget") }));

    const closed = mountYandexButton("yandex-id-1", "client", LOOK, onShown);

    await expect(closed).rejects.not.toBeInstanceOf(YandexIdUnavailableError);
    expect(onShown).toHaveBeenCalledOnce();
  });
});
