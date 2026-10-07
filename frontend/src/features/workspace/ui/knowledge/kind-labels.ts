import type { KnowledgeKind } from "../../domain/knowledge-contract";
import type { KnowledgeWords } from "./knowledge-words";

/** What each kind of knowledge is called in lists, in the interface language. */
export const kindLabel = (t: KnowledgeWords, kind: KnowledgeKind) => t(`kind.${kind}`);
