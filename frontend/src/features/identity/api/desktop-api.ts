import { apiClient } from "@/lib/api/app-client";
import { dataOf } from "@/lib/api/client";

/** Одноразовый код для десктоп-приложения; с вызовом PKCE, если приложение его прислало. */
export async function issueDesktopCode(codeChallenge: string | null): Promise<string> {
  const body = codeChallenge === null ? null : { code_challenge: codeChallenge, code_challenge_method: "S256" };
  const answer = await dataOf(apiClient.POST("/v1/auth/desktop/code", { body }));
  return answer.code;
}
