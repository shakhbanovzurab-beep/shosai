import { type LocalParticipant, Track } from "livekit-client";

import { BOARD_FPS, BOARD_TRACK } from "../domain/board-protocol";

/*
 * Доска в записи встречи: запись сводит опубликованные дорожки комнаты, а доска рисуется у каждого локально.
 * Пока идёт запись, сохраняющий публикует холсты редактора одной дорожкой «демонстрации экрана» — шаблон записи
 * показывает её крупно. Кадры рисуются по таймеру: редактор трогает холст только при правках, и неподвижная
 * доска иначе перестала бы отдавать кадры.
 */

const MAX_BITRATE = 1_200_000;

// Холстов у редактора несколько (сцена и слой взаимодействия поверх): сводятся все, в порядке DOM.
function draw(target: HTMLCanvasElement, sources: readonly HTMLCanvasElement[]) {
  const [first] = sources;
  if (!first) return;
  if (target.width !== first.width || target.height !== first.height) {
    target.width = first.width;
    target.height = first.height;
  }
  const context = target.getContext("2d");
  if (!context) return;
  context.fillStyle = "#ffffff";
  context.fillRect(0, 0, target.width, target.height);
  for (const source of sources) if (source.width > 0 && source.height > 0) context.drawImage(source, 0, 0);
}

/** Опубликовать холсты доски из контейнера; функция снимает дорожку. Своя демонстрация экрана — важнее. */
export function streamBoard(participant: LocalParticipant, container: HTMLElement): () => void {
  if (participant.getTrackPublication(Track.Source.ScreenShare)) return () => undefined;
  const sources = [...container.querySelectorAll<HTMLCanvasElement>("canvas.excalidraw__canvas")];
  if (sources.length === 0) return () => undefined;
  const target = document.createElement("canvas");
  draw(target, sources);
  const timer = window.setInterval(() => draw(target, sources), 1_000 / BOARD_FPS);
  const [track] = target.captureStream(BOARD_FPS).getVideoTracks();
  if (!track) {
    window.clearInterval(timer);
    return () => undefined;
  }
  const published = participant
    .publishTrack(track, {
      name: BOARD_TRACK,
      source: Track.Source.ScreenShare,
      videoEncoding: { maxFramerate: BOARD_FPS, maxBitrate: MAX_BITRATE },
      // Смазанный текст на доске бесполезен, а подтормаживающий читается: при нехватке полосы — кадры, не чёткость.
      degradationPreference: "maintain-resolution",
    })
    .then(() => true)
    .catch(() => false);
  return () => {
    window.clearInterval(timer);
    void published.then(async (done) => {
      if (done) await participant.unpublishTrack(track, true);
      else track.stop();
    });
  };
}
