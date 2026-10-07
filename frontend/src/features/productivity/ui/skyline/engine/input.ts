import { hitCell } from "../../../domain/skyline/cells";
import { ELEV_3D, ELEV_RANGE, YAW_3D, YAW_RANGE } from "../../../domain/skyline/scene";
import type { Engine } from "./state";
import { kick, orbitCursor, refreshActive } from "./tick";

type Drag = { id: number; x: number; y: number; yaw: number; elev: number; moved: boolean; orbit: boolean };

const NAV_KEYS = ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End", "Escape", "Enter", " "];

const select = (E: Engine, i: number) => {
  const c = E.cfg.current.model.cells[i];
  if (c) E.cfg.current.onCellClick?.({ date: c.date, count: c.count });
};

/**
 * Hover, tap, drag-to-orbit and keyboard navigation. Returns a cleanup. The chart is drawn left to right in every
 * language (see contribution-skyline.tsx), so the arrow keys follow the drawing: ArrowLeft is the week before.
 */
export const attachInput = (E: Engine) => {
  const { canvas } = E;
  let drag: (Drag & { mouse: boolean }) | null = null;

  const local = (ev: PointerEvent) => {
    const r = canvas.getBoundingClientRect();
    return [ev.clientX - r.left, ev.clientY - r.top] as const;
  };

  const onDown = (ev: PointerEvent) => {
    if (ev.button !== 0) return;
    const orbit = E.cfg.current.orbit && E.target === 1;
    const mouse = ev.pointerType === "mouse";
    drag = {
      id: ev.pointerId,
      x: ev.clientX,
      y: ev.clientY,
      yaw: E.yawGoal,
      elev: E.elevGoal,
      moved: false,
      orbit,
      mouse,
    };
    if (orbit) {
      try {
        canvas.setPointerCapture(ev.pointerId);
      } catch {
        /* capture is a nicety */
      }
    }
  };

  const onMove = (ev: PointerEvent) => {
    if (drag?.orbit && ev.pointerId === drag.id) {
      const dx = ev.clientX - drag.x;
      const dy = ev.clientY - drag.y;
      if (drag.moved || Math.hypot(dx, dy) > 4) {
        drag.moved = true;
        E.yawGoal = Math.min(YAW_RANGE[1] - YAW_3D, Math.max(YAW_RANGE[0] - YAW_3D, drag.yaw + dx * 0.006));
        if (drag.mouse) {
          E.elevGoal = Math.min(ELEV_RANGE[1] - ELEV_3D, Math.max(ELEV_RANGE[0] - ELEV_3D, drag.elev + dy * 0.004));
        }
        canvas.style.cursor = "grabbing";
        E.hovered = -1;
        refreshActive(E);
        kick(E);
        return;
      }
    }
    if (ev.pointerType !== "mouse") return;
    const [x, y] = local(ev);
    const i = hitCell(E, x, y);
    if (i !== E.hovered) {
      E.hovered = i;
      refreshActive(E);
    }
    const orbitable = E.cfg.current.orbit && E.target === 1;
    if (orbitable) canvas.style.cursor = "grab";
    else canvas.style.cursor = i >= 0 ? "pointer" : "default";
  };

  const onUp = (ev: PointerEvent) => {
    if (!drag || ev.pointerId !== drag.id) return;
    const wasMoved = drag.moved;
    drag = null;
    if (canvas.hasPointerCapture(ev.pointerId)) canvas.releasePointerCapture(ev.pointerId);
    canvas.style.cursor = orbitCursor(E);
    if (wasMoved) return;
    const [x, y] = local(ev);
    const i = hitCell(E, x, y);
    E.pinned = i === E.pinned ? -1 : i;
    if (ev.pointerType !== "mouse") E.hovered = -1;
    refreshActive(E);
    if (i >= 0) select(E, i);
  };

  const onCancel = () => {
    drag = null;
  };

  const onLeave = () => {
    if (drag) return;
    E.hovered = -1;
    refreshActive(E);
  };

  const onDbl = () => {
    E.yawGoal = 0;
    E.elevGoal = 0;
    kick(E);
  };

  const onKey = (ev: KeyboardEvent) => {
    if (!NAV_KEYS.includes(ev.key) || !E.n) return;
    ev.preventDefault();
    if (ev.key === "Escape") {
      E.pinned = -1;
      E.hovered = -1;
      refreshActive(E);
      return;
    }
    const started = E.pinned >= 0 || E.activeIdx >= 0;
    let i = E.n - 1;
    if (E.pinned >= 0) i = E.pinned;
    else if (E.activeIdx >= 0) i = E.activeIdx;
    if (ev.key === "Enter" || ev.key === " ") {
      select(E, i);
      return;
    }
    if (started) {
      if (ev.key === "ArrowLeft") i -= 7;
      if (ev.key === "ArrowRight") i += 7;
      if (ev.key === "ArrowUp") i -= 1;
      if (ev.key === "ArrowDown") i += 1;
      if (ev.key === "Home") i = 0;
      if (ev.key === "End") i = E.n - 1;
    }
    i = Math.max(0, Math.min(E.n - 1, i));
    E.pinned = i;
    E.hovered = -1;
    refreshActive(E);
    E.cfg.current.setAnnounce(E.cfg.current.describe(i));
  };

  const onBlur = () => {
    E.pinned = -1;
    refreshActive(E);
  };

  const listeners = [
    ["pointerdown", onDown],
    ["pointermove", onMove],
    ["pointerup", onUp],
    ["pointercancel", onCancel],
    ["pointerleave", onLeave],
    ["dblclick", onDbl],
    ["keydown", onKey],
    ["blur", onBlur],
  ] as const;
  for (const [type, fn] of listeners) canvas.addEventListener(type, fn as EventListener);
  return () => {
    for (const [type, fn] of listeners) canvas.removeEventListener(type, fn as EventListener);
  };
};
