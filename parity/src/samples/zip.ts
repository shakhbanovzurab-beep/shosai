// Архив ZIP без сжатия: из него собраны образцы DOCX и XLSX. Время записей
// постоянное (1980-01-01 00:00), поэтому одинаковые файлы дают одинаковые байты.

import { crc32 } from "node:zlib";

export interface ZipEntry {
  readonly name: string;
  readonly text: string;
}

/** Дата DOS 1980-01-01: год 0, месяц 1, день 1. */
const DOS_DATE = (1 << 5) | 1;

function header(signature: number, size: number): Buffer {
  const buffer = Buffer.alloc(size);
  buffer.writeUInt32LE(signature, 0);
  return buffer;
}

/** Поля, общие для локального заголовка и записи каталога: версия … длина имени. */
function common(buffer: Buffer, offset: number, crc: number, size: number, nameLength: number): void {
  buffer.writeUInt16LE(20, offset); // версия для распаковки 2.0
  buffer.writeUInt16LE(0, offset + 2); // флаги
  buffer.writeUInt16LE(0, offset + 4); // метод: без сжатия
  buffer.writeUInt16LE(0, offset + 6); // время
  buffer.writeUInt16LE(DOS_DATE, offset + 8);
  buffer.writeUInt32LE(crc, offset + 10);
  buffer.writeUInt32LE(size, offset + 14); // сжатый размер
  buffer.writeUInt32LE(size, offset + 18); // исходный размер
  buffer.writeUInt16LE(nameLength, offset + 22);
}

export function zip(entries: readonly ZipEntry[]): Buffer {
  const locals: Buffer[] = [];
  const central: Buffer[] = [];
  let offset = 0;
  for (const entry of entries) {
    const name = Buffer.from(entry.name, "utf8");
    const data = Buffer.from(entry.text, "utf8");
    const crc = crc32(data);
    const local = header(0x04034b50, 30);
    common(local, 4, crc, data.length, name.length);
    locals.push(local, name, data);
    const record = header(0x02014b50, 46);
    record.writeUInt16LE(20, 4); // создано версией 2.0
    common(record, 6, crc, data.length, name.length);
    record.writeUInt32LE(offset, 42);
    central.push(record, name);
    offset += local.length + name.length + data.length;
  }
  const directory = Buffer.concat(central);
  const end = header(0x06054b50, 22);
  end.writeUInt16LE(entries.length, 8);
  end.writeUInt16LE(entries.length, 10);
  end.writeUInt32LE(directory.length, 12);
  end.writeUInt32LE(offset, 16);
  return Buffer.concat([...locals, directory, end]);
}
