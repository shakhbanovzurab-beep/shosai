import type { ReactNode } from "react";

import type { useTranslations } from "use-intl";

import type { LeoContext } from "../domain/context";

/** Leo's translator, for wording outside a component. */
export type LeoT = ReturnType<typeof useTranslations<"leo">>;

/** Where Leo works as its panel shows it: the header, what it sees, the line under the input, and a notice. */
export type LeoPlace = { label: string; scope: string; caption: string | null; notice: ReactNode };

export function leoPlace(t: LeoT, context: LeoContext, notice: ReactNode): LeoPlace {
  if (context.kind === "workspace") {
    const name = context.name;
    return { label: t("place.workspace", { name }), scope: t("place.scopeWorkspace", { name }), caption: null, notice };
  }
  if (context.kind === "hub") {
    const name = context.name;
    return {
      label: t("place.hub", { name }),
      scope: t("place.scopeHub", { name }),
      caption: t("place.boundHub", { name }),
      notice,
    };
  }
  return { label: t("place.personal"), scope: t("place.scopePersonal"), caption: null, notice };
}
