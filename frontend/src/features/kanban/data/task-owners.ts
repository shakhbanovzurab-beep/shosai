import type { TaskOwnerProfile } from "../domain/board";

export const taskOwners = {
  arham: {
    name: "Arham Khan",
    tone: "zinc",
  },
  junaid: {
    name: "Ethan Brooks",
    tone: "lime",
  },
  maya: {
    name: "Hannah Reed",
    tone: "indigo",
  },
  meera: {
    name: "Rohan Iyer",
    tone: "fuchsia",
  },
  nisha: {
    name: "Nora Bennett",
    tone: "violet",
  },
  rahul: {
    name: "Vikram Menon",
    tone: "pink",
  },
  sara: {
    name: "Clara Hughes",
    tone: "sky",
  },
} satisfies Record<string, TaskOwnerProfile>;
