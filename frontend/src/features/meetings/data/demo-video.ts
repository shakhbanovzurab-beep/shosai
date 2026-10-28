/* Видео демо-участников: холст с цветом и инициалами как поток камеры, чтобы сцена выглядела живой на моках. */

const HUES = [210, 160, 28, 280, 340, 190, 95];
const FRAME = { width: 640, height: 360 };

function hueOf(identity: string) {
  let hash = 0;
  for (const char of identity) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
  return HUES[hash % HUES.length] ?? 210;
}

/** Поток «камеры» демо-участника: медленно дышащий цвет и его инициалы; null, где холст не умеет поток. */
export function demoCameraStream(identity: string, initials: string): { stream: MediaStream; stop: () => void } | null {
  const canvas = document.createElement("canvas");
  canvas.width = FRAME.width;
  canvas.height = FRAME.height;
  const context = canvas.getContext("2d");
  if (!context || typeof canvas.captureStream !== "function") return null;
  const hue = hueOf(identity);
  let frame = 0;
  const draw = () => {
    frame += 1;
    const light = 34 + Math.sin(frame / 40) * 6;
    context.fillStyle = `hsl(${hue} 45% ${light}%)`;
    context.fillRect(0, 0, FRAME.width, FRAME.height);
    context.fillStyle = "rgb(255 255 255 / 0.85)";
    context.font = "600 96px system-ui, sans-serif";
    context.textAlign = "center";
    context.textBaseline = "middle";
    context.fillText(initials, FRAME.width / 2, FRAME.height / 2);
  };
  draw();
  const timer = window.setInterval(draw, 66);
  const stream = canvas.captureStream(15);
  return {
    stream,
    stop: () => {
      window.clearInterval(timer);
      for (const track of stream.getTracks()) track.stop();
    },
  };
}
