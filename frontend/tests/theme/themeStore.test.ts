import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

/** Подставная настройка системы: тёмная ли тема и подписчики на её смену. */
function stubSystemTheme(dark: boolean) {
  const listeners = new Set<() => void>();
  const query = {
    get matches() {
      return dark;
    },
    addEventListener: (_type: string, listener: () => void) => listeners.add(listener),
    removeEventListener: (_type: string, listener: () => void) => listeners.delete(listener),
  };
  vi.stubGlobal("matchMedia", () => query);
  return {
    listeners,
    change(next: boolean) {
      dark = next;
      for (const listener of listeners) listener();
    },
  };
}

/** Свежий модуль стора: у каждого теста своё замыкание и своё состояние. */
const loadStore = async () => {
  vi.resetModules();
  return import("@/core/theme/themeStore");
};

const root = document.documentElement;

describe("стор оформления", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    localStorage.clear();
    document.head.replaceChildren();
    root.lang = "ru";
    root.className = "";
    root.setAttribute("data-theme", "light");
    root.removeAttribute("data-font");
  });

  afterEach(() => {
    vi.useRealTimers();
    localStorage.clear();
  });

  it("startTheme поднимает выбор устройства на документ и в стор", async () => {
    localStorage.setItem("wh.theme", "dark");
    localStorage.setItem("wh.appearance", JSON.stringify({ font: "serif" }));
    const { startTheme, useThemeStore } = await loadStore();
    startTheme();
    expect(useThemeStore.getState()).toMatchObject({ pref: "dark", theme: "dark", font: "serif" });
    expect(root.getAttribute("data-theme")).toBe("dark");
    expect(root.getAttribute("data-font")).toBe("serif");
    expect(root.classList.contains("theme-anim")).toBe(false);
  });

  it("переключение темы пишет wh.theme и плавно меняет цвета 400 мс", async () => {
    const { startTheme, useThemeStore } = await loadStore();
    startTheme();
    useThemeStore.getState().toggle();
    expect(useThemeStore.getState()).toMatchObject({ pref: "dark", theme: "dark" });
    expect(root.getAttribute("data-theme")).toBe("dark");
    expect(localStorage.getItem("wh.theme")).toBe("dark");
    expect(root.classList.contains("theme-anim")).toBe(true);
    vi.advanceTimersByTime(399);
    useThemeStore.getState().toggle();
    vi.advanceTimersByTime(399);
    expect(root.classList.contains("theme-anim")).toBe(true);
    vi.advanceTimersByTime(1);
    expect(root.classList.contains("theme-anim")).toBe(false);
    expect(root.getAttribute("data-theme")).toBe("light");
  });

  it("«Система» следует смене системной темы, пока выбрана", async () => {
    const system = stubSystemTheme(false);
    const { startTheme, useThemeStore } = await loadStore();
    const stop = startTheme();
    useThemeStore.getState().setPref("system");
    expect(useThemeStore.getState().theme).toBe("light");
    system.change(true);
    expect(useThemeStore.getState()).toMatchObject({ pref: "system", theme: "dark" });
    useThemeStore.getState().setPref("light");
    system.change(false);
    system.change(true);
    expect(useThemeStore.getState().theme).toBe("light");
    stop();
    expect(system.listeners.size).toBe(0);
  });

  it("выбор шрифта ставит роль, сохраняет её и подключает объявления", async () => {
    const { useThemeStore } = await loadStore();
    useThemeStore.getState().setFont("mono");
    expect(root.getAttribute("data-font")).toBe("mono");
    expect(JSON.parse(localStorage.getItem("wh.appearance") ?? "null")).toEqual({ font: "mono" });
    expect(document.head.querySelector('link[href="/fonts/roles-ru-mono.css"]')).not.toBeNull();
    useThemeStore.getState().setFont("whisperer");
    expect(root.hasAttribute("data-font")).toBe(false);
  });

  it("шрифт из профиля не откатывает выбор, сделанный здесь меньше 5 с назад", async () => {
    const { useThemeStore } = await loadStore();
    useThemeStore.getState().setFont("serif");
    vi.advanceTimersByTime(4_999);
    useThemeStore.getState().adoptServerAppearance({ font: "sans" });
    expect(useThemeStore.getState().font).toBe("serif");
    vi.advanceTimersByTime(1);
    useThemeStore.getState().adoptServerAppearance({ font: "sans" });
    expect(useThemeStore.getState().font).toBe("sans");
    expect(root.getAttribute("data-font")).toBe("sans");
    expect(JSON.parse(localStorage.getItem("wh.appearance") ?? "null")).toEqual({ font: "sans" });
  });

  it("принимает оформление профиля сразу, если здесь его не меняли; мусор — фирменное", async () => {
    const { useThemeStore } = await loadStore();
    useThemeStore.getState().adoptServerAppearance({ font: "alt" });
    expect(useThemeStore.getState().font).toBe("sans");
    useThemeStore.getState().adoptServerAppearance("сломано");
    expect(useThemeStore.getState().font).toBe("whisperer");
  });

  it("без хранилища тема переключается и живёт до перезагрузки", async () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new DOMException("квота", "QuotaExceededError");
    });
    const { startTheme, useThemeStore } = await loadStore();
    startTheme();
    useThemeStore.getState().setPref("dark");
    expect(root.getAttribute("data-theme")).toBe("dark");
    expect(localStorage.getItem("wh.theme")).toBeNull();
  });
});
