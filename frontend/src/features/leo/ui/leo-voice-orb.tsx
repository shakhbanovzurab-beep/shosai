"use client";

import * as React from "react";

import { MODE_FRAMES, type OrbState, paintFrame, resolvePreset } from "thinking-orbs/engine";

import { usePreferencesStore } from "@/features/preferences/model/preferences-provider";

// Рисунок сферы выверен для 64 px; крупнее он масштабируется векторно, а холст — в размере показа.
const DESIGN = 64;
// Потолок плотности: на экране 3x холст 160 px — уже 480 точек, дальше разницы не видно.
const MAX_DPR = 3;
// Кадр без движения, когда человек просит меньше анимации, — тот же, что у библиотеки.
const STILL_SECONDS = 0.6;

/**
 * Сфера голосового режима. `ThinkingOrb` рисует холст в размере своего пресета (не больше 64 px), и CSS
 * растягивал его до 160 px — размыто. Здесь холст в размере показа на плотность экрана, рисунок тот же.
 */
export function LeoVoiceOrb({ state, size }: { readonly state: OrbState; readonly size: number }) {
  const canvasRef = React.useRef<HTMLCanvasElement>(null);
  const dark = usePreferencesStore((store) => store.resolvedThemeMode === "dark");

  React.useEffect(() => {
    const canvas = canvasRef.current;
    const context = canvas?.getContext("2d");
    if (!canvas || !context) return;
    const density = Math.min(MAX_DPR, window.devicePixelRatio || 1);
    canvas.width = Math.round(size * density);
    canvas.height = Math.round(size * density);
    const scale = (size / DESIGN) * density;
    const { mode, speed, opts } = resolvePreset(state, DESIGN);
    const draw = (seconds: number) => {
      context.setTransform(scale, 0, 0, scale, 0, 0);
      context.clearRect(0, 0, DESIGN, DESIGN);
      paintFrame(context, MODE_FRAMES[mode](DESIGN, seconds, opts), dark);
    };
    const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
    let frame = 0;
    const loop = (now: number) => {
      draw((now / 1000) * speed);
      frame = requestAnimationFrame(loop);
    };
    const restart = () => {
      cancelAnimationFrame(frame);
      if (motion.matches) draw(STILL_SECONDS);
      else frame = requestAnimationFrame(loop);
    };
    restart();
    motion.addEventListener("change", restart);
    return () => {
      cancelAnimationFrame(frame);
      motion.removeEventListener("change", restart);
    };
  }, [state, size, dark]);

  return <canvas ref={canvasRef} className="block" style={{ width: size, height: size }} />;
}
