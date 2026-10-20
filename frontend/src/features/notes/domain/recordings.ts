export const MAX_RECORDING_BYTES = 25 * 1024 * 1024;
export const RECORDING_ACCEPT = "audio/*,video/*";

/**
 * Название, которое сервер даст встрече из записи: имя файла без последнего расширения (`PurePosixPath.stem`).
 * Карточка загрузки показывает его же, поэтому, когда встреча приходит на её место, строка заголовка не меняется.
 */
export function recordingTitle(fileName: string): string {
  const dot = fileName.lastIndexOf(".");
  return dot > 0 && dot < fileName.length - 1 ? fileName.slice(0, dot) : fileName;
}
