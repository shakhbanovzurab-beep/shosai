import { draw } from "./draw";
import { attachInput } from "./input";
import { load, relayout, retheme } from "./layout";
import { createEngine, type EngineConfig, type EngineElements } from "./state";
import { kick, setTarget } from "./tick";

export type EngineHandle = {
  kick: () => void;
  load: () => void;
  retheme: () => void;
  tipWidth: (w: number) => void;
  destroy: () => void;
};

/** Attributes the preferences runtime sets on <html> when the theme mode or preset changes. */
const THEME_ATTRIBUTES = ["class", "style", "data-theme-mode", "data-theme-preset"];

export const mountEngine = (els: EngineElements, cfg: { current: EngineConfig }): EngineHandle => {
  const reduceMq = window.matchMedia("(prefers-reduced-motion: reduce)");
  const darkMq = window.matchMedia("(prefers-color-scheme: dark)");
  const E = createEngine(els, cfg, reduceMq.matches);
  const onTheme = () => retheme(E);

  load(E);
  retheme(E);
  relayout(E);

  // The 3D view rises out of the flat one the first time it is seen.
  const enter = () => {
    if (E.entered) return;
    E.entered = true;
    if (E.reduced) E.t = cfg.current.target;
    setTarget(E);
  };
  let io: IntersectionObserver | null = null;
  if ("IntersectionObserver" in window) {
    io = new IntersectionObserver(
      (entries) => {
        if (!entries.some((en) => en.isIntersecting)) return;
        enter();
        io?.disconnect();
      },
      { threshold: 0.35 },
    );
    io.observe(els.stage);
  } else enter();

  const ro = new ResizeObserver(() => {
    if (Math.round(els.stage.clientWidth) !== E.W) relayout(E);
  });
  ro.observe(els.stage);

  // Theme changes land a frame after the attribute flips; read colours once styles have settled.
  const mo = new MutationObserver(() => requestAnimationFrame(onTheme));
  mo.observe(document.documentElement, { attributes: true, attributeFilter: THEME_ATTRIBUTES });
  const onReduce = () => {
    E.reduced = reduceMq.matches;
    kick(E);
  };
  reduceMq.addEventListener("change", onReduce);
  darkMq.addEventListener("change", onTheme);
  const detachInput = attachInput(E);

  return {
    kick: () => {
      setTarget(E);
      kick(E);
    },
    load: () => {
      load(E);
      retheme(E);
      relayout(E);
    },
    retheme: onTheme,
    tipWidth: (w) => {
      E.tipW = w;
      draw(E);
    },
    destroy: () => {
      if (E.raf) cancelAnimationFrame(E.raf);
      io?.disconnect();
      ro.disconnect();
      mo.disconnect();
      reduceMq.removeEventListener("change", onReduce);
      darkMq.removeEventListener("change", onTheme);
      detachInput();
    },
  };
};
