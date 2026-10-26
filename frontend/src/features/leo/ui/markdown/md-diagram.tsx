"use client";

import { type ReactNode, useEffect, useLayoutEffect, useRef, useState } from "react";

import { useTranslations } from "use-intl";

import { usePreferencesStore } from "@/features/preferences/model/preferences-provider";

import { CopyAction } from "../leo-message-actions";
import { useDiagrams } from "./lazy-renderers";

type Drawn = { readonly key: string; readonly svg: string | null };

/**
 * Диаграмма Mermaid ответа в рамке блока кода: «Копировать» берёт её текст. Рисуется заново со сменой темы или
 * пресета, прежний рисунок стоит, пока готовится новый; не нарисовалась — `children` (её текст кодом) с пометкой.
 */
export function MdDiagram({ source, children }: { readonly source: string; readonly children: ReactNode }) {
  const t = useTranslations("leo");
  const diagrams = useDiagrams();
  const dark = usePreferencesStore((store) => store.resolvedThemeMode === "dark");
  const preset = usePreferencesStore((store) => store.values.theme_preset);
  const key = `${dark}:${preset}:${source}`;
  const [drawn, setDrawn] = useState<Drawn | null>(null);
  const canvas = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (diagrams === null) return;
    let current = true;
    diagrams.renderDiagram(source, diagrams.pageTheme(dark)).then(
      (svg) => {
        if (current) setDrawn({ key, svg });
      },
      (error: unknown) => {
        console.warn("Leo: диаграмма не нарисовалась", error);
        if (current) setDrawn({ key, svg: null });
      },
    );
    return () => {
      current = false;
    };
  }, [diagrams, source, dark, key]);

  const svg = drawn?.svg ?? null;
  useLayoutEffect(() => {
    if (diagrams !== null && svg !== null && canvas.current !== null) diagrams.placeDiagram(svg, canvas.current);
  }, [diagrams, svg]);

  if (drawn !== null && drawn.key === key && drawn.svg === null) {
    return (
      <div className="flex flex-col gap-1.5">
        <p className="text-muted-foreground text-xs">{t("diagram.failed")}</p>
        {children}
      </div>
    );
  }
  return (
    <figure aria-label={t("diagram.label")} className="overflow-hidden rounded-lg border bg-card">
      <div className="flex h-8 items-center justify-between gap-2 border-b ps-3 pe-1">
        <span className="text-muted-foreground text-xs">{t("diagram.label")}</span>
        <CopyAction text={source} />
      </div>
      {svg === null ? (
        <div className="m-3 h-32 animate-pulse rounded-md bg-muted/60 motion-reduce:animate-none" />
      ) : (
        <div ref={canvas} dir="ltr" className="overflow-x-auto p-3 [&_svg]:mx-auto [&_svg]:block [&_svg]:h-auto" />
      )}
    </figure>
  );
}
