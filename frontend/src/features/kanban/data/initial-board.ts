import type { BoardState, Column } from "../domain/board";
import { buildingTasks, qaTasks, shippedTasks } from "./delivery-tasks";
import { column } from "./demo-rows";
import { ideaTasks, plannedTasks } from "./upcoming-tasks";

/** The demo "Work" board: a product team's delivery flow. */
export const workColumns: Column[] = [
  column("ideas", "Ideas", "todo"),
  column("planned", "Planned", "todo"),
  column("building", "Building", "in_progress"),
  column("qa", "QA", "in_progress"),
  column("shipped", "Shipped", "done"),
];

export const workTasks: BoardState = {
  ideas: ideaTasks,
  planned: plannedTasks,
  building: buildingTasks,
  qa: qaTasks,
  shipped: shippedTasks,
};
