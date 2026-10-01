// Образцы картинки и PDF для просмотра в «Файлах». Просмотр открывает их по
// подписанной ссылке S3; ссылку и сам объект на стенде подставляет
// serve/object-store.ts. Картинка рисуется кодом: одинаковые байты при любом запуске.

import { crc32, deflateSync } from "node:zlib";

type Rgb = readonly [number, number, number];

const PAPER: Rgb = [244, 241, 234];
const YELLOW: Rgb = [255, 216, 77];
const INK: Rgb = [31, 41, 55];

function chunk(type: string, data: Buffer): Buffer {
  const length = Buffer.alloc(4);
  length.writeUInt32BE(data.length);
  const body = Buffer.concat([Buffer.from(type, "ascii"), data]);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(body));
  return Buffer.concat([length, body, crc]);
}

/** Логотип: жёлтый круг с тёмным треугольником «A» и три полосы надписи. */
function logoPixel(x: number, y: number): Rgb {
  const dx = x - 200;
  const dy = y - 200;
  if (dx * dx + dy * dy <= 130 * 130) {
    // Треугольник вершиной вверх: от (200, 110) до основания y = 280.
    const half = ((y - 110) / 170) * 90;
    const inside = y >= 110 && y <= 280 && Math.abs(dx) <= half;
    const hole = y >= 200 && y <= 280 && Math.abs(dx) <= half - 34;
    return inside && !hole ? INK : YELLOW;
  }
  const bars = [[150, 200, 560], [195, 215, 500], [240, 260, 530]] as const;
  return bars.some(([top, bottom, right]) => y >= top && y < bottom && x >= 370 && x < right) ? INK : PAPER;
}

/** «Логотип_Acme.png», 640 × 400. */
export function acmeLogoPng(): Buffer {
  const width = 640;
  const height = 400;
  const raw = Buffer.alloc((width * 3 + 1) * height);
  for (let y = 0; y < height; y += 1) {
    const row = y * (width * 3 + 1);
    raw[row] = 0; // фильтр строки: без преобразования
    for (let x = 0; x < width; x += 1) {
      const [r, g, b] = logoPixel(x, y);
      raw.set([r, g, b], row + 1 + x * 3);
    }
  }
  const header = Buffer.alloc(13);
  header.writeUInt32BE(width, 0);
  header.writeUInt32BE(height, 4);
  header.set([8, 2, 0, 0, 0], 8); // 8 бит, RGB, без чересстрочности
  const signature = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
  return Buffer.concat([signature, chunk("IHDR", header), chunk("IDAT", deflateSync(raw, { level: 9 })), chunk("IEND", Buffer.alloc(0))]);
}

/** «Прайс_2025.pdf»: одна страница A4 с заголовком; таблица ссылок считается по байтам. */
export function priceListPdf(): Buffer {
  const content = "BT /F1 24 Tf 72 760 Td (Acme price list 2025) Tj ET";
  const objects = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
    `<< /Length ${content.length} >>\nstream\n${content}\nendstream`,
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
  ];
  let body = "%PDF-1.4\n";
  const offsets: number[] = [];
  objects.forEach((object, index) => {
    offsets.push(body.length);
    body += `${index + 1} 0 obj\n${object}\nendobj\n`;
  });
  const xref = body.length;
  body += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
  body += offsets.map((offset) => `${String(offset).padStart(10, "0")} 00000 n \n`).join("");
  body += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  return Buffer.from(body, "latin1");
}
