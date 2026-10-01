// Матрица съёмки: охват состояний по ячейкам и теги проектов.

import { expect, test } from "@playwright/test";

import { allCells, cellsFor, SWEEP_LANGUAGES } from "./matrix.ts";

const names = (cells: ReadonlyArray<{ name: string }>): string[] => cells.map((cell) => cell.name).sort();

test("full — 8 ячеек на ru и en, single — одна, на компьютере в светлой теме", () => {
  expect(cellsFor("full", ["ru", "en"], false)).toHaveLength(8);
  expect(names(cellsFor("single", ["ru"], false))).toEqual(["desktop-light-ru"]);
});

test("только английская фикстура даёт только английские ячейки", () => {
  expect(names(cellsFor("full", ["en"], false))).toEqual([
    "desktop-dark-en",
    "desktop-light-en",
    "mobile-dark-en",
    "mobile-light-en",
  ]);
});

test("ограничение вьюпортов: состояние только телефона", () => {
  expect(names(cellsFor("full", ["ru"], false, ["mobile"]))).toEqual(["mobile-dark-ru", "mobile-light-ru"]);
  expect(names(cellsFor("single", ["ru"], false, ["mobile"]))).toEqual(["mobile-light-ru"]);
});

test("прогон по языкам добавляет 14 языков на двух вьюпортах в светлой теме", () => {
  expect(cellsFor("full", ["ru", "en"], true)).toHaveLength(8 + SWEEP_LANGUAGES.length * 2);
  expect(allCells()).toHaveLength(8 + SWEEP_LANGUAGES.length * 2);
});
