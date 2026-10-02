import { isValidElement, StrictMode, type ReactNode } from "react";
import type { createRoot as CreateRoot } from "react-dom/client";
import { beforeEach, describe, expect, it, vi } from "vitest";

// Одна и та же подмена на все повторные загрузки модуля точки входа.
const { createRoot } = vi.hoisted(() => ({ createRoot: vi.fn<typeof CreateRoot>() }));
vi.mock("react-dom/client", () => ({ createRoot }));

describe("точка входа", () => {
  beforeEach(() => {
    vi.resetModules();
    document.body.replaceChildren();
  });

  it("монтирует корень приложения в #root в строгом режиме", async () => {
    const render = vi.fn<(children: ReactNode) => void>();
    createRoot.mockReturnValue({ render, unmount: vi.fn() });
    const container = document.createElement("div");
    container.id = "root";
    document.body.append(container);

    await import("@/entrypoints/main");
    const { AppRoot } = await import("@/composition/AppRoot");

    expect(createRoot).toHaveBeenCalledExactlyOnceWith(container);
    expect(render).toHaveBeenCalledOnce();
    const element = render.mock.calls[0]?.[0];
    expect(isValidElement<{ children: ReactNode }>(element) && element.type).toBe(StrictMode);
    const child = isValidElement<{ children: ReactNode }>(element) ? element.props.children : null;
    expect(isValidElement(child) && child.type).toBe(AppRoot);
  });

  it("без #root падает сразу и ничего не монтирует", async () => {
    await expect(import("@/entrypoints/main")).rejects.toThrow("#root");
    expect(createRoot).not.toHaveBeenCalled();
  });
});
