// Каждое состояние инвентаризации снято, видно на другом снимке или исключено
// с причиной — и разбор таблиц инвентаризации, на котором держится эта проверка.

import path from "node:path";

import { expect, test } from "@playwright/test";

import { PARITY_ROOT } from "../config.ts";
import { ALL_STATES } from "../states/registry.ts";
import { cellStateRefs, inventoryGaps, matchesPattern, parseInventoryGroup, readInventoryGroups } from "./coverage.ts";

test("каждое состояние инвентаризации снято или разобрано в разделе покрытия", () => {
  const groups = readInventoryGroups(path.join(PARITY_ROOT, "inventory"));
  expect(groups.length).toBeGreaterThan(0);
  expect(inventoryGaps(groups, ALL_STATES.map((state) => state.id))).toEqual([]);
});

test("варианты в ячейке раскрываются от полного id, пояснения в скобках не читаются", () => {
  expect(cellStateRefs(" `billing.renewal.not-eligible` / `on` / `.off` ").map((ref) => ref.candidates)).toEqual([
    ["billing.renewal.not-eligible"],
    ["billing.renewal.on", "billing.on", "billing.renewal.not-eligible.on"],
    ["billing.renewal.off", "billing.off", "billing.renewal.not-eligible.off"],
  ]);
  expect(cellStateRefs(" context.saving / saved (bug) ").map((ref) => ref.text)).toEqual(["context.saving", "saved"]);
  expect(cellStateRefs(" `rooms.room.translator.failure-<code>` ")[0]?.text).toBe("rooms.room.translator.failure-*");
  expect(cellStateRefs(" state id ")).toEqual([]);
});

test("шаблон id: звёздочка — любой фрагмент, хвост через точку или дефис может отсутствовать", () => {
  expect(matchesPattern("onboarding.tour.step-*.cta", "onboarding.tour.step-3.cta")).toBe(true);
  expect(matchesPattern("onboarding.tour.step-*.cta", "onboarding.tour.step-3")).toBe(false);
  expect(matchesPattern("livekit.room.expanded.*", "livekit.room.expanded-loading")).toBe(true);
  expect(matchesPattern("livekit.room.expanded.*", "livekit.room.expanded")).toBe(true);
  expect(matchesPattern("livekit.room.expanded.*", "livekit.room.expandedx")).toBe(false);
  expect(matchesPattern("analytics.calendar.year-*", "analytics.calendar.year")).toBe(true);
  expect(matchesPattern("a.b", "a.b")).toBe(true);
});

test("состояние без снимка и без строки покрытия — пробел; строка покрытия его закрывает", () => {
  const inventory = [
    "| state id | how |",
    "|---|---|",
    "| `shop.cart.empty` / `.populated` / `.error` | … |",
    "| `shop.cart.item-*` | … |",
    "",
    "### Coverage in the screenshot matrix (step 9 of D2)",
    "",
    "| state | reason |",
    "|---|---|",
  ].join("\n");
  const registered = ["shop.cart.empty", "shop.cart.populated", "shop.cart.item-removed"];
  expect(inventoryGaps([parseInventoryGroup("shop.md", inventory)], registered)).toEqual(["shop.md: shop.cart.error"]);
  const tooBroad = `${inventory}\n| \`en\` cells of \`shop.*\` | the page is not translated |`;
  expect(inventoryGaps([parseInventoryGroup("shop.md", tooBroad)], registered)).toEqual(["shop.md: shop.cart.error"]);
  const covered = `${inventory}\n| \`shop.cart.error\` | the request never fails in the recording stack |`;
  expect(inventoryGaps([parseInventoryGroup("shop.md", covered)], registered)).toEqual([]);
});
