"use client";

import { Blocks } from "lucide-react";
import { useFormatter, useTranslations } from "use-intl";

import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { usePollingResource } from "@/hooks/use-polling-resource";

import { type Connector, connectorProblemOf, isConnectorCategory } from "../../domain/connectors-contract";
import { connectorsResource } from "../../model/settings-resources";
import { SectionState } from "../section-state";
import { ConnectorActionsProvider } from "./connector-actions-context";
import { ConnectorLogo } from "./connector-logo";
import { ConnectorStatus } from "./connector-status";

function ConnectorName({ connector }: { connector: Connector }) {
  const t = useTranslations("settingsConnectors");
  const format = useFormatter();
  const problem = connector.status === "needs_reconnect" ? connectorProblemOf(connector.problem) : null;
  // Согласие тестового проекта Google живёт неделю: строка заранее говорит, до какого дня.
  const reconnectBy = connector.status === "connected" ? connector.reconnect_by : null;
  return (
    <div className="flex items-center gap-3">
      <ConnectorLogo id={connector.id} />
      <div className="flex min-w-0 flex-col">
        <span className="font-medium">{connector.name}</span>
        {connector.account ? (
          <span dir="auto" className="truncate text-muted-foreground text-xs">
            {connector.account}
          </span>
        ) : null}
        {reconnectBy ? (
          <span className="text-muted-foreground text-xs">
            {t("reconnectBy", { date: format.dateTime(new Date(reconnectBy), "medium") })}
          </span>
        ) : null}
        {connector.status === "needs_reconnect" ? (
          <span className="text-destructive text-xs">
            {problem === null ? t("needsReconnect") : t(`problems.${problem}`)}
          </span>
        ) : null}
      </div>
    </div>
  );
}

function NoConnectors() {
  const t = useTranslations("settingsConnectors");
  return (
    <Empty className="border">
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <Blocks />
        </EmptyMedia>
        <EmptyTitle>{t("empty.title")}</EmptyTitle>
        <EmptyDescription>{t("empty.body")}</EmptyDescription>
      </EmptyHeader>
    </Empty>
  );
}

function ConnectorRow({ connector }: { connector: Connector }) {
  const t = useTranslations("settingsConnectors");
  const category = connector.category;
  return (
    <TableRow>
      <TableCell className="whitespace-normal">
        <ConnectorName connector={connector} />
      </TableCell>
      <TableCell className="text-muted-foreground">
        {isConnectorCategory(category) ? t(`categories.${category}`) : null}
      </TableCell>
      <TableCell>
        <ConnectorStatus connector={connector} />
      </TableCell>
    </TableRow>
  );
}

/** The apps Leo and the rest of Shosai can use, connected once through the provider's consent or a given secret. */
export function ConnectorsSection() {
  const t = useTranslations("settingsConnectors");
  const state = usePollingResource(connectorsResource);

  return (
    <div className="flex flex-col gap-4">
      <p className="text-muted-foreground text-sm">{t("description")}</p>
      <SectionState state={state} onRetry={() => void connectorsResource.refresh()}>
        {({ items }) =>
          items.length === 0 ? (
            <NoConnectors />
          ) : (
            <ConnectorActionsProvider>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="text-start">{t("columns.connector")}</TableHead>
                    <TableHead className="w-36 text-start">{t("columns.type")}</TableHead>
                    <TableHead className="w-44 text-start">{t("columns.status")}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items.map((connector) => (
                    <ConnectorRow key={connector.id} connector={connector} />
                  ))}
                </TableBody>
              </Table>
            </ConnectorActionsProvider>
          )
        }
      </SectionState>
    </div>
  );
}
