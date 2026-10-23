import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { mountVkOneTap } from "./vk-widget";

// Подписки поддельного OneTap: тест сам шлёт события SDK.
const subscriptions = vi.hoisted(() => new Map<string, (payload: unknown) => void>());

vi.mock("../api/social-api", () => ({
  startVkWidget: vi.fn(async () => ({ state: "state-1", code_challenge: "hash", redirect_url: "https://shosai.test" })),
}));

vi.mock("@vkid/sdk", () => ({
  Config: { init: vi.fn() },
  ConfigResponseMode: { Callback: "callback" },
  Scheme: { LIGHT: "light", DARK: "dark" },
  WidgetEvents: { ERROR: "error" },
  OneTapInternalEvents: { LOGIN_SUCCESS: "login_success" },
  OneTap: class {
    render() {
      return this;
    }
    on(event: string, handler: (payload: unknown) => void) {
      subscriptions.set(event, handler);
      return this;
    }
    close() {
      subscriptions.clear();
    }
  },
}));

const LOOK = { theme: "light", language: "ru", next: "/app" } as const;

// Контейнер, в корне виджета которого SDK уже записал своё состояние.
function container(state: string | null): HTMLElement {
  const root = { getAttribute: () => state };
  return { querySelector: () => (state === null ? null : root) } as unknown as HTMLElement;
}

function events() {
  return { onShown: vi.fn(), onCode: vi.fn(), onFailed: vi.fn() };
}

beforeEach(() => {
  vi.stubGlobal(
    "MutationObserver",
    class {
      observe = vi.fn();
      disconnect = vi.fn();
    },
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
  subscriptions.clear();
});

describe("mountVkOneTap", () => {
  it("keeps the SDK's widget when it reports an error, as when its frame times out through a VPN", async () => {
    const watching = events();
    await mountVkOneTap(container("not_loaded"), 54823060, LOOK, watching);

    subscriptions.get("error")?.({ code: 0, text: "timeout" });

    expect(watching.onFailed).not.toHaveBeenCalled();
    expect(watching.onShown).toHaveBeenCalledOnce();
  });

  it("waits until the SDK has drawn a button", async () => {
    const watching = events();
    await mountVkOneTap(container("loading"), 54823060, LOOK, watching);

    expect(watching.onShown).not.toHaveBeenCalled();
  });

  it("hands over the code, the state and the device id", async () => {
    const watching = events();
    await mountVkOneTap(container("loaded"), 54823060, LOOK, watching);

    subscriptions.get("login_success")?.({ code: "code-1", state: "state-1", device_id: "device-1" });

    expect(watching.onCode).toHaveBeenCalledWith({ code: "code-1", state: "state-1", deviceId: "device-1" });
  });

  it("fails when the SDK signs in without a code", async () => {
    const watching = events();
    await mountVkOneTap(container("loaded"), 54823060, LOOK, watching);

    subscriptions.get("login_success")?.({ state: "state-1", device_id: "device-1" });

    expect(watching.onFailed).toHaveBeenCalledOnce();
    expect(watching.onCode).not.toHaveBeenCalled();
  });
});
