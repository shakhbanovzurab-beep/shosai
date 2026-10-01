// Образцы документов для просмотра в «Файлах»: приложение к договору (DOCX) и
// смета пилота (XLSX). S3 у стенда записи нет, и черновик отдаёт содержимое
// файла пустым — просмотр показал бы ошибку разбора. Минимальные, но настоящие
// документы Office: mammoth и SheetJS разбирают их так же, как файлы из Word и Excel.

import { zip } from "./zip.ts";

const XML = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>';
const RELS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships";
const PACKAGE_RELS = "http://schemas.openxmlformats.org/package/2006/relationships";
const W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main";
const S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main";

const escape = (text: string): string => text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

const paragraph = (text: string, style?: string): string =>
  `<w:p>${style === undefined ? "" : `<w:pPr><w:pStyle w:val="${style}"/></w:pPr>`}<w:r><w:t xml:space="preserve">${escape(text)}</w:t></w:r></w:p>`;

const cell = (text: string): string => `<w:tc>${paragraph(text)}</w:tc>`;

const SLA_ROWS: readonly (readonly [string, string, string])[] = [
  ["Показатель", "Цель", "Окно измерения"],
  ["Доступность сервиса", "99,9 %", "Календарный месяц"],
  ["Реакция на инцидент P1", "30 минут", "Круглосуточно"],
  ["Реакция на инцидент P2", "4 часа", "Рабочие дни"],
];

const SLA_BODY = [
  paragraph("Приложение 1. Соглашение об уровне обслуживания", "Heading1"),
  paragraph("Приложение действует вместе с договором № 2026-07 между Acme и Whisperer."),
  paragraph("Показатели обслуживания", "Heading2"),
  `<w:tbl>${SLA_ROWS.map((row) => `<w:tr>${row.map(cell).join("")}</w:tr>`).join("")}</w:tbl>`,
  paragraph("Отчёт о показателях Whisperer присылает до пятого числа следующего месяца."),
].join("");

const HEADING_STYLES = [1, 2]
  .map((level) => `<w:style w:type="paragraph" w:styleId="Heading${level}"><w:name w:val="heading ${level}"/></w:style>`)
  .join("");

/** «Приложение_1_SLA.docx»: заголовки, абзацы и таблица показателей. */
export function slaDocx(): Buffer {
  return zip([
    {
      name: "[Content_Types].xml",
      text: `${XML}<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">` +
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>' +
        '<Default Extension="xml" ContentType="application/xml"/>' +
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>' +
        '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>' +
        "</Types>",
    },
    {
      name: "_rels/.rels",
      text: `${XML}<Relationships xmlns="${PACKAGE_RELS}"><Relationship Id="rId1" Type="${RELS}/officeDocument" Target="word/document.xml"/></Relationships>`,
    },
    {
      name: "word/_rels/document.xml.rels",
      text: `${XML}<Relationships xmlns="${PACKAGE_RELS}"><Relationship Id="rId1" Type="${RELS}/styles" Target="styles.xml"/></Relationships>`,
    },
    { name: "word/styles.xml", text: `${XML}<w:styles xmlns:w="${W}">${HEADING_STYLES}</w:styles>` },
    { name: "word/document.xml", text: `${XML}<w:document xmlns:w="${W}"><w:body>${SLA_BODY}</w:body></w:document>` },
  ]);
}

const ESTIMATE: readonly (readonly (string | number)[])[] = [
  ["Статья", "Количество", "Цена, ₽", "Сумма, ₽"],
  ["Лицензии Pro", 40, 1990, 79_600],
  ["Внедрение и настройка SSO", 1, 120_000, 120_000],
  ["Обучение администраторов", 2, 35_000, 70_000],
  ["Итого", "", "", 269_600],
];

const column = (index: number): string => String.fromCharCode(65 + index);

function sheetCell(value: string | number, row: number, index: number): string {
  const reference = `${column(index)}${row}`;
  if (typeof value === "number") return `<c r="${reference}"><v>${value}</v></c>`;
  return `<c r="${reference}" t="inlineStr"><is><t>${escape(value)}</t></is></c>`;
}

/** «Смета_пилота_Acme_v2.xlsx»: один лист сметы с итогом. */
export function estimateXlsx(): Buffer {
  const rows = ESTIMATE.map((values, index) =>
    `<row r="${index + 1}">${values.map((value, cellIndex) => sheetCell(value, index + 1, cellIndex)).join("")}</row>`).join("");
  return zip([
    {
      name: "[Content_Types].xml",
      text: `${XML}<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">` +
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>' +
        '<Default Extension="xml" ContentType="application/xml"/>' +
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>' +
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' +
        "</Types>",
    },
    {
      name: "_rels/.rels",
      text: `${XML}<Relationships xmlns="${PACKAGE_RELS}"><Relationship Id="rId1" Type="${RELS}/officeDocument" Target="xl/workbook.xml"/></Relationships>`,
    },
    {
      name: "xl/_rels/workbook.xml.rels",
      text: `${XML}<Relationships xmlns="${PACKAGE_RELS}"><Relationship Id="rId1" Type="${RELS}/worksheet" Target="worksheets/sheet1.xml"/></Relationships>`,
    },
    {
      name: "xl/workbook.xml",
      text: `${XML}<workbook xmlns="${S}" xmlns:r="${RELS}"><sheets><sheet name="Смета" sheetId="1" r:id="rId1"/></sheets></workbook>`,
    },
    { name: "xl/worksheets/sheet1.xml", text: `${XML}<worksheet xmlns="${S}"><sheetData>${rows}</sheetData></worksheet>` },
  ]);
}
