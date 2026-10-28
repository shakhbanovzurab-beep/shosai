/* Длительность идущей встречи на часах звонка: «4:07», «59:59», «1:02:03» — как в шапке Zoom. */

const pad = (value: number) => String(value).padStart(2, "0");

/** Прошедшее с начала встречи время в виде часов; до начала и при сбитых часах — «0:00». */
export function callClock(startedAt: number, now: number): string {
  const seconds = Math.max(0, Math.floor((now - startedAt) / 1000));
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const rest = seconds % 60;
  return hours > 0 ? `${hours}:${pad(minutes)}:${pad(rest)}` : `${minutes}:${pad(rest)}`;
}
