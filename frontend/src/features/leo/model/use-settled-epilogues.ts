import * as React from "react";

import { useQueryClient } from "@tanstack/react-query";

import type { Epilogue } from "../domain/epilogues";
import { allThreadsKey, messagesKey } from "./agent-thread";
import { dropEpilogues } from "./epilogues";

/**
 * Дочитанные эпилоги уступают место истории: их треды перечитываются, и только потом эпилоги убираются — ответ не
 * мигает прежним видом. Эпилог, который вела главная без панели, уберёт первая открытая панель.
 */
export function useSettledEpilogues(epilogues: readonly Epilogue[]) {
  const queryClient = useQueryClient();
  React.useEffect(() => {
    const settled = epilogues.filter((epilogue) => epilogue.ended);
    if (settled.length === 0) return;
    const threads = new Set(settled.flatMap((epilogue) => (epilogue.threadId === null ? [] : [epilogue.threadId])));
    const reread = [...threads].map((threadId) => queryClient.invalidateQueries({ queryKey: messagesKey(threadId) }));
    void queryClient.invalidateQueries({ queryKey: allThreadsKey });
    void Promise.allSettled(reread).then(() => dropEpilogues(new Set(settled.map((epilogue) => epilogue.runId))));
  }, [epilogues, queryClient]);
}
