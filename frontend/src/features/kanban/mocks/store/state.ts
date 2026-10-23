import type { ChatTaskRecord } from "./types";

/*
 * Задачи, которые моки чатов создают из одобренной карточки «Сделать задачей» (TK-D13), пока у chats нет API.
 * Доска и панель читают настоящий API задач (план tasks, шаг 9); здесь моки чатов и Лео проверяют, что задача
 * создана с источником из чата. Одно хранилище на страницу, на globalThis, как хранилища других слайсов.
 */

type KanbanDemo = { tasks: Map<string, ChatTaskRecord> };

const shared = globalThis as typeof globalThis & { kanbanChatTasks?: KanbanDemo };

export function demo(): KanbanDemo {
  shared.kanbanChatTasks ??= { tasks: new Map() };
  return shared.kanbanChatTasks;
}

/** Начать с пустого хранилища — для тестов. */
export function resetDemo() {
  shared.kanbanChatTasks = { tasks: new Map() };
  return shared.kanbanChatTasks;
}
