import { businessZoneLabel, useBusinessZone } from "@/features/admin-sign-in/model/business-zone";

import type { DisplayZone } from "../domain/format";

/** Деловой пояс платформы и его подпись: в нём карточки показывают даты (ADR 0058). */
export function useDisplayZone(): DisplayZone {
  const zone = useBusinessZone();
  return { zone, label: businessZoneLabel(zone) };
}
