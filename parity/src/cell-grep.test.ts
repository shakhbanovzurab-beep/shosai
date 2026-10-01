// Выражения отбора соответствуют матрице: каждая ячейка есть и совпадает только
// со своим тегом.

import { expect, test } from "@playwright/test";

import { CELL_GREP } from "./cell-grep.ts";
import { allCells, cellTag } from "./matrix.ts";

test("у каждой ячейки матрицы есть выражение отбора, лишних нет", () => {
  expect(Object.keys(CELL_GREP).sort()).toEqual(allCells().map((cell) => cell.name).sort());
});

test("выражение ячейки совпадает с её тегом и ни с одним другим", () => {
  const names = allCells().map((cell) => cell.name);
  for (const name of names) {
    const pattern = CELL_GREP[name];
    expect(pattern, name).toBeDefined();
    for (const other of names) {
      expect(pattern?.test(`state.id ${cellTag(other)} ${cellTag("x")}`), `${name} против ${other}`).toBe(name === other);
    }
  }
});
