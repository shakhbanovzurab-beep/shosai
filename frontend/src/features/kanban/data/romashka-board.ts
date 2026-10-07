import type { BoardState, Column } from "../domain/board";
import { column, demoTask } from "./demo-rows";
import { taskOwners } from "./task-owners";

/** The demo "Romashka" board: where the Romashka rollout hub sends the work agreed in its meetings. */
export const romashkaColumns: Column[] = [
  column("romashka-todo", "To do", "todo"),
  column("romashka-doing", "In progress", "in_progress"),
  column("romashka-done", "Done", "done"),
];

const team = "Romashka";

export const romashkaTasks: BoardState = {
  "romashka-todo": [
    demoTask("romashka-sso", "Set up SSO access for Romashka admins", "", {
      priority: "High",
      due: "2026-10-05",
      team,
    }),
    demoTask("romashka-training", "Run the admin training session", "", { team }),
  ],
  "romashka-doing": [
    demoTask("romashka-mockup", "Interface mockup without Telegram", "", {
      progress: 60,
      owner: taskOwners.arham,
      team,
    }),
  ],
  "romashka-done": [demoTask("romashka-pilot-users", "Collect the pilot user list", "", { priority: "Low", team })],
};
