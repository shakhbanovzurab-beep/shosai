import { type AgentRoutes, agentApi, operatorRoutes } from "../api/agent-api";
import type { LeoContext } from "../domain/context";
import type { LeoMessage } from "../domain/types";
import type { LeoChat } from "./leo-chat";

/*
 * Чей разговор ведёт Leo на API и что в нём можно. Человек ходит в свои маршруты, прикладывает файлы и оценивает
 * ответы; оператор платформы в админке — в свои (AG-D5): вложений его ход не принимает, а оценки собираются только
 * с ответов людям (AG-D13).
 */

export interface AgentChannel {
  readonly owner: LeoChat["owner"];
  readonly routes: AgentRoutes;
  /** К вопросу можно приложить файлы (`leo_attachment`, шаг 12 агента). */
  readonly attachments: boolean;
  /** Ответ можно оценить. */
  readonly ratings: boolean;
}

const PERSON: AgentChannel = { owner: "person", routes: agentApi, attachments: true, ratings: true };
const OPERATOR: AgentChannel = { owner: "operator", routes: operatorRoutes, attachments: false, ratings: false };

export const channelOf = (context: LeoContext): AgentChannel => (context.kind === "platform" ? OPERATOR : PERSON);

const unrated = (message: LeoMessage): LeoMessage =>
  message.feedback === undefined ? message : { ...message, feedback: undefined };

/** Разговор, каким его показывает панель: без кнопок оценки там, где оценок нет. */
export const shownIn = (channel: AgentChannel, messages: LeoMessage[]): LeoMessage[] =>
  channel.ratings ? messages : messages.map(unrated);
