import type { KnowledgeItem } from "./knowledge-contract";

export const isSource = (item: KnowledgeItem) => item.source.kind === "connector";
