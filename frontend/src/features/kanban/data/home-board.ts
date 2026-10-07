import type { BoardState, Column } from "../domain/board";
import { column, demoTask } from "./demo-rows";
import { taskOwners } from "./task-owners";

/** The demo "Home" board: personal errands on the simple template. */
export const homeColumns: Column[] = [
  column("home-todo", "To do", "todo"),
  column("home-doing", "In progress", "in_progress"),
  column("home-done", "Done", "done"),
];

const owner = taskOwners.arham;

export const homeTasks: BoardState = {
  "home-todo": [
    demoTask("home-dentist", "Book a dentist appointment", "", {
      priority: "High",
      due: "2026-10-10",
      owner,
      team: "Health",
    }),
    demoTask("home-insurance", "Renew car insurance", "", { due: "2026-10-18", owner, team: "Finance" }),
    demoTask("home-trip", "Plan the weekend trip", "Pick a place, book the cabin and check the weather.", {
      priority: "Low",
      owner,
      team: "Family",
    }),
  ],
  "home-doing": [
    demoTask("home-taxes", "Gather documents for taxes", "", {
      progress: 40,
      due: "2026-10-31",
      owner,
      team: "Finance",
    }),
    demoTask("home-shelves", "Fix the kitchen shelves", "", { progress: 70, owner, team: "Home" }),
  ],
  "home-done": [demoTask("home-groceries", "Order groceries", "", { priority: "Low", owner, team: "Errands" })],
};
