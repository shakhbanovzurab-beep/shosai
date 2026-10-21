"use client";

import { useSyncExternalStore } from "react";

/*
 * Панель задачи живёт в адресе (`?task=<id>`): ссылка открывает её, «Назад» закрывает. Адрес меняется без
 * перехода роутера: страница и доска остаются на месте, а на изменение подписана только панель — сотни
 * карточек не перерисовываются, когда она открывается.
 */

const TASK_PARAM = "task";
const listeners = new Set<() => void>();

function go(change: (url: URL) => void) {
  const url = new URL(window.location.href);
  change(url);
  window.history.pushState(null, "", `${url.pathname}${url.search}`);
  for (const listener of listeners) listener();
}

export const openTask = (taskId: string) => go((url) => url.searchParams.set(TASK_PARAM, taskId));
export const closeTask = () => go((url) => url.searchParams.delete(TASK_PARAM));

function subscribe(listener: () => void) {
  listeners.add(listener);
  window.addEventListener("popstate", listener);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("popstate", listener);
  };
}

const read = () => new URLSearchParams(window.location.search).get(TASK_PARAM);

/** Задача, открытая в панели, или null. */
export const useOpenTaskId = () => useSyncExternalStore(subscribe, read, () => null);
