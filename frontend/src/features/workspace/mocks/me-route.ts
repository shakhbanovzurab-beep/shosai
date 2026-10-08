import { JsonResponse } from "@/mocks/runtime";

import type {
  MyKnowledgeResponse,
  MyMeetingsResponse,
  MySharesResponse,
  MyTasksResponse,
} from "../domain/personal-contract";
import { myKnowledge, myMeetings, myShares, myTasks } from "./personal";

/** /api/me/tasks: tasks assigned to the account in every workspace, for Productivity and Kanban. */
export const myTasksRoute = {
  async GET(_request: Request) {
    return JsonResponse.json<MyTasksResponse>({ tasks: myTasks() });
  },
};

/** /api/me/meetings: meetings others shared with the account, per workspace. */
export const myMeetingsRoute = {
  async GET(_request: Request) {
    return JsonResponse.json<MyMeetingsResponse>(myMeetings());
  },
};

/** /api/me/shares: where the account's recordings and files are shared. */
export const mySharesRoute = {
  async GET(_request: Request) {
    return JsonResponse.json<MySharesResponse>(myShares());
  },
};

/** /api/me/knowledge: what Leo may use from each workspace when the account is in Personal. */
export const myKnowledgeRoute = {
  async GET(_request: Request) {
    return JsonResponse.json<MyKnowledgeResponse>(myKnowledge());
  },
};
