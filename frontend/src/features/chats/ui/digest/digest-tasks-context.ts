import { createContext } from "react";

/** Задачи из пунктов дайджеста: какие готовятся, как сделать и как показать карточку одобрения. */
export type DigestTasks = {
  making: ReadonlySet<string>;
  make: (itemIds: string[]) => void;
  showProposal: (proposalId: string) => void;
};

export const DigestTasksContext = createContext<DigestTasks | null>(null);
