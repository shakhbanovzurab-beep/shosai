/*
 * Изменения из потоков Leo, применяемые раз за кадр: ответ, приходящий десятками кусков в секунду, перерисовывается
 * не чаще экрана. Каждое хранилище ставит свои изменения и своё оповещение; после кадра оно оповещает один раз.
 */

let queued: Array<() => void> = [];
const notifiers = new Set<() => void>();
let scheduled = false;

function flush() {
  scheduled = false;
  const work = queued;
  const notify = [...notifiers];
  queued = [];
  notifiers.clear();
  for (const step of work) step();
  for (const listener of notify) listener();
}

/** Изменение хранилища — на ближайшем кадре; `notify` хранилища зовётся после всех изменений кадра. */
export function onNextFrame(change: () => void, notify: () => void) {
  queued.push(change);
  notifiers.add(notify);
  if (scheduled) return;
  scheduled = true;
  if (typeof requestAnimationFrame === "function") requestAnimationFrame(flush);
  else setTimeout(flush, 0);
}

/** Применить накопленное сейчас: перед концом хода ответ должен быть целым. */
export function flushFrame() {
  if (scheduled) flush();
}
