// Образцы файлов: устойчивые байты и целая структура (PNG, PDF, ZIP).

import { inflateSync } from "node:zlib";

import { expect, test } from "@playwright/test";

import { acmeLogoPng, priceListPdf } from "./images.ts";
import { estimateXlsx, slaDocx } from "./office.ts";

/** Имена файлов архива из центрального каталога. */
function zipNames(archive: Buffer): string[] {
  const end = archive.lastIndexOf(Buffer.from([0x50, 0x4b, 0x05, 0x06]));
  let offset = archive.readUInt32LE(end + 16);
  const names: string[] = [];
  for (let index = 0; index < archive.readUInt16LE(end + 10); index += 1) {
    expect(archive.readUInt32LE(offset)).toBe(0x02014b50);
    const nameLength = archive.readUInt16LE(offset + 28);
    names.push(archive.subarray(offset + 46, offset + 46 + nameLength).toString("utf8"));
    offset += 46 + nameLength;
  }
  return names;
}

test("образцы одинаковы при каждом построении", () => {
  for (const build of [acmeLogoPng, priceListPdf, slaDocx, estimateXlsx]) expect(build().equals(build())).toBe(true);
});

test("PNG: подпись, размер 640 × 400 и полный набор строк", () => {
  const png = acmeLogoPng();
  expect(png.subarray(0, 8).toString("hex")).toBe("89504e470d0a1a0a");
  expect([png.readUInt32BE(16), png.readUInt32BE(20)]).toEqual([640, 400]);
  const idatLength = png.readUInt32BE(33);
  expect(inflateSync(png.subarray(41, 41 + idatLength)).length).toBe((640 * 3 + 1) * 400);
});

test("PDF: таблица ссылок указывает на начало каждого объекта", () => {
  const pdf = priceListPdf().toString("latin1");
  const xref = Number(/startxref\n(\d+)/.exec(pdf)?.[1]);
  expect(pdf.slice(xref, xref + 4)).toBe("xref");
  const offsets = [...pdf.slice(xref).matchAll(/^(\d{10}) 00000 n $/gm)].map((match) => Number(match[1]));
  offsets.forEach((offset, index) => expect(pdf.slice(offset).startsWith(`${index + 1} 0 obj`)).toBe(true));
});

test("DOCX и XLSX: части пакета Office на своих местах", () => {
  expect(zipNames(slaDocx())).toEqual(["[Content_Types].xml", "_rels/.rels", "word/_rels/document.xml.rels", "word/styles.xml", "word/document.xml"]);
  expect(zipNames(estimateXlsx())).toEqual(["[Content_Types].xml", "_rels/.rels", "xl/_rels/workbook.xml.rels", "xl/workbook.xml", "xl/worksheets/sheet1.xml"]);
});
