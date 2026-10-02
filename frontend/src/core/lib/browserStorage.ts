/**
 * Чтение и запись localStorage без исключений.
 *
 * Хранилище недоступно в приватном режиме, при заблокированных данных сайта и
 * при переполненной квоте. Для настроек этого устройства (тема, шрифт, язык)
 * это штатный случай, а не сбой: настройка действует до перезагрузки, а
 * вызывающий получает явный ответ — `null` или `false` — и сам выбирает замену.
 */

export function readLocal(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

/** `true`, если значение записано. */
export function writeLocal(key: string, value: string): boolean {
  try {
    window.localStorage.setItem(key, value);
    return true;
  } catch {
    return false;
  }
}
