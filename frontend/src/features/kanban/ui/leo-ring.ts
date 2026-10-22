import { scaleRadii } from "thinking-orbs";
import { MODE_FRAMES, paintFrame, resolvePreset } from "thinking-orbs/engine";

/*
 * Живое кольцо Leo на метках доски — одно на всех. У каждого `ThinkingOrb` свой цикл, и он сам считает кадр
 * 60 раз в секунду: четыре метки на доске «Work» занимали 18 % главного потока. Здесь кадр считается и рисуется
 * один раз, в каждую видимую метку он только копируется. Метки вне экрана не рисуются; фоновая вкладка и
 * уменьшение движения останавливают цикл — тогда виден неподвижный кадр, как у библиотеки.
 */

const SIZE = 20;
const STILL_SECONDS = 0.6;
const { mode, speed, opts } = resolvePreset("breathing", SIZE);
const ringOpts = scaleRadii(opts, 1.3);
const frameAt = MODE_FRAMES[mode];

const attached = new Set<HTMLCanvasElement>();
const visible = new Set<HTMLCanvasElement>();
let source: HTMLCanvasElement | null = null;
let raf = 0;

const reducedMotion = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
const isDark = () => document.documentElement.classList.contains("dark");

/** Нарисовать кадр момента `seconds` один раз и скопировать его в `targets`. */
function render(seconds: number, targets: Iterable<HTMLCanvasElement>) {
  source ??= document.createElement("canvas");
  const scale = window.devicePixelRatio || 1;
  const pixels = Math.round(SIZE * scale);
  if (source.width !== pixels) Object.assign(source, { width: pixels, height: pixels });
  const ctx = source.getContext("2d");
  if (!ctx) return;
  ctx.setTransform(scale, 0, 0, scale, 0, 0);
  ctx.clearRect(0, 0, SIZE, SIZE);
  paintFrame(ctx, frameAt(SIZE, seconds, ringOpts), isDark());
  for (const canvas of targets) {
    if (canvas.width !== pixels) Object.assign(canvas, { width: pixels, height: pixels });
    const target = canvas.getContext("2d");
    target?.clearRect(0, 0, pixels, pixels);
    target?.drawImage(source, 0, 0);
  }
}

const now = () => (performance.now() / 1000) * speed;

// Кольцо дышит медленно: 30 кадров в секунду на глаз не отличить от 60, а считать вдвое меньше.
const FRAME_MS = 1000 / 30;
let drawnAt = 0;

function loop(time: number) {
  raf = 0;
  if (visible.size === 0 || document.visibilityState === "hidden") return;
  if (reducedMotion()) return render(STILL_SECONDS, attached);
  if (time - drawnAt >= FRAME_MS - 1) {
    drawnAt = time;
    render(now(), visible);
  }
  raf = requestAnimationFrame(loop);
}

const wake = () => {
  if (!raf) raf = requestAnimationFrame(loop);
};

/** Видимость меток, вкладка, уменьшение движения и тема — одни наблюдатели на все метки. */
function watch() {
  const sight = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      const canvas = entry.target as HTMLCanvasElement;
      if (entry.isIntersecting) visible.add(canvas);
      else visible.delete(canvas);
    }
    wake();
  });
  const motion = matchMedia("(prefers-reduced-motion: reduce)");
  // Тема сменилась, пока кольцо стоит: неподвижный кадр перерисовывается в новых цветах.
  const theme = new MutationObserver(() => (raf ? undefined : render(STILL_SECONDS, attached)));
  theme.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
  document.addEventListener("visibilitychange", wake);
  motion.addEventListener("change", wake);
  return {
    sight,
    stop() {
      sight.disconnect();
      theme.disconnect();
      document.removeEventListener("visibilitychange", wake);
      motion.removeEventListener("change", wake);
      cancelAnimationFrame(raf);
      raf = 0;
    },
  };
}

let observers: ReturnType<typeof watch> | null = null;

/** Ref холста метки: кольцо оживает, пока метка на экране; возвращает уборку. */
export function attachLeoRing(canvas: HTMLCanvasElement | null) {
  if (!canvas) return;
  attached.add(canvas);
  render(reducedMotion() ? STILL_SECONDS : now(), [canvas]);
  observers ??= watch();
  observers.sight.observe(canvas);
  return () => {
    attached.delete(canvas);
    visible.delete(canvas);
    observers?.sight.unobserve(canvas);
    if (attached.size === 0) {
      observers?.stop();
      observers = null;
    }
  };
}
