// Порция работы — не дольше этого, если браузер не сказал, сколько у него свободного времени.
const SLICE_MS = 8;

/**
 * Выполняет `step`, пока он возвращает true, порциями в простое браузера (`requestIdleCallback`, где его нет —
 * `setTimeout`), чтобы не занимать кадры, в которые человек что-то делает. Возвращает отмену.
 */
export function idleChunks(step: () => boolean): () => void {
  let cancelled = false;
  let handle: number | undefined;
  // В Safari requestIdleCallback может не быть: тогда порции идут через setTimeout.
  const hasIdle = typeof (window as Partial<Window>).requestIdleCallback === "function";

  const run = (deadline?: IdleDeadline) => {
    const until = performance.now() + SLICE_MS;
    const hasTime = () => (deadline ? deadline.timeRemaining() > 1 : performance.now() < until);
    let more = true;
    while (!cancelled && more && hasTime()) more = step();
    if (!cancelled && more) schedule();
  };
  const schedule = () => {
    handle = hasIdle ? window.requestIdleCallback(run) : window.setTimeout(run, 0);
  };

  schedule();
  return () => {
    cancelled = true;
    if (handle === undefined) return;
    if (hasIdle) window.cancelIdleCallback(handle);
    else window.clearTimeout(handle);
  };
}
