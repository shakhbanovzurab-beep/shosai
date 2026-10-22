import type { Card } from "../../domain/tasks-contract";

/** Есть ли у карточки что показать внизу, кроме исполнителя: чат-источник, подзадачи, вложения, комментарии. */
export const hasFooterFacts = (card: Card) =>
  card.source_chat !== null || card.subtasks_total > 0 || card.comment_count > 0 || card.attachment_count > 0;
