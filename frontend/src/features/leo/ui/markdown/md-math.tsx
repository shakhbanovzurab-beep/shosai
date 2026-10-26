"use client";

import { useLayoutEffect, useRef } from "react";

import { cn } from "cn";

import { useMath } from "./lazy-renderers";

/** Формула ответа, в строке или блоком; пока KaTeX грузится, на её месте исходник TeX. */
export function MdMath({ tex, display }: { readonly tex: string; readonly display: boolean }) {
  const math = useMath();
  const ref = useRef<HTMLSpanElement>(null);

  // До отрисовки кадра: формула появляется сразу готовой, без пустого места на кадр.
  useLayoutEffect(() => {
    if (math !== null && ref.current !== null) math.renderMath(tex, ref.current, display);
  }, [math, tex, display]);

  if (math === null) {
    return (
      <code dir="ltr" className={cn("font-mono text-[0.85em] text-muted-foreground", display && "block")}>
        {tex}
      </code>
    );
  }
  return <span ref={ref} dir="ltr" className={cn(display && "block overflow-x-auto overflow-y-hidden py-1")} />;
}
