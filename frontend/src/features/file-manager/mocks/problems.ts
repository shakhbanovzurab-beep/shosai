import { JsonResponse } from "@/mocks/runtime";

/*
 * Why the demo refuses a request, answered like the backend (ADR 0008): the envelope carries the code the
 * cabinet words in the user's language, and its numbers.
 */

export type Problem = { code: string; status: number; params?: Record<string, number> };

export const isProblem = (value: object): value is Problem => "code" in value && "status" in value;

export const problem = (code: string, status: number, params?: Record<string, number>): Problem => ({
  code,
  status,
  params,
});

/** The refusal in the backend's envelope, with a request id as the server would add. */
export function refuse({ code, status, params }: Problem) {
  const error = { code, request_id: `demo-${crypto.randomUUID()}`, ...(params ? { params } : {}) };
  return JsonResponse.json({ error, detail: code }, { status });
}
