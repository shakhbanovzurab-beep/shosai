"use client";

import { hubApi } from "../api/hub-api";
import type { HubSignal } from "../domain/contract";

const claims = new Map<string, Promise<HubSignal | null>>();

/**
 * The assistant's signal for a hub, claimed once per page session: the server delivers it at most
 * once a day, so asking again would only come back empty. A failure is silence, never an error.
 */
export function claimSignal(hubId: string) {
  let claim = claims.get(hubId);
  if (!claim) {
    claim = hubApi.claimSignal(hubId).then(
      (response) => response.signal,
      () => null,
    );
    claims.set(hubId, claim);
  }
  return claim;
}
