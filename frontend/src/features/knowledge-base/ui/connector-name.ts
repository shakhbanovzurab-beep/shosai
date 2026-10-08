"use client";

import { useTranslations } from "use-intl";

import type { ConnectorDefinition } from "../domain/connectors";

/** A source's name as the user reads it: its brand, or the catalog's word for the one generic source (Website). */
export function useConnectorName() {
  const t = useTranslations("knowledgeBaseSources");
  return (definition: ConnectorDefinition) => definition.brand ?? t("website");
}
