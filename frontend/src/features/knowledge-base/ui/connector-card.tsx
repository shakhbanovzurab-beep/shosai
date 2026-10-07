"use client";

import { MoreVertical, RefreshCw, Settings2, Unplug } from "lucide-react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Spinner } from "@/components/ui/spinner";

import type { ConnectorDefinition } from "../domain/connectors";
import { BUSY_CONNECTOR, type Connector } from "../domain/contract";
import { syncSource } from "../model/connector-actions";
import { ConnectorIcon } from "./connector-icon";
import { useConnectorName } from "./connector-name";
import { ConnectorDetails } from "./connector-status";

type ConnectorCardProps = {
  definition: ConnectorDefinition;
  connector: Connector;
  onConfigure: () => void;
  onDisconnect: () => void;
};

function ConnectorMenu({ definition, connector, onConfigure, onDisconnect }: ConnectorCardProps) {
  const t = useTranslations("knowledgeBaseSources");
  const common = useTranslations("common");
  const name = useConnectorName()(definition);
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon-sm" aria-label={common("actionsFor", { name })}>
          <MoreVertical />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-44">
        <DropdownMenuItem
          disabled={BUSY_CONNECTOR.has(connector.status)}
          onSelect={() => void syncSource(definition, name, t)}
        >
          <RefreshCw />
          {t("card.syncNow")}
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={onConfigure}>
          <Settings2 />
          {t("card.settings")}
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem variant="destructive" onSelect={onDisconnect}>
          <Unplug />
          {t("card.disconnect")}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function SyncButton({ definition, busy }: { definition: ConnectorDefinition; busy: boolean }) {
  const t = useTranslations("knowledgeBaseSources");
  const name = useConnectorName()(definition);
  return (
    <Button
      variant="outline"
      size="sm"
      className="w-full"
      disabled={busy}
      onClick={() => void syncSource(definition, name, t)}
    >
      {busy ? <Spinner data-icon="inline-start" /> : <RefreshCw data-icon="inline-start" />}
      {busy ? t("card.syncing") : t("card.syncNow")}
    </Button>
  );
}

export function ConnectorCard(props: ConnectorCardProps) {
  const { definition, connector, onConfigure } = props;
  const t = useTranslations("knowledgeBaseSources");
  const name = useConnectorName()(definition);
  const linked = connector.status !== "disconnected";

  return (
    <Card className="shadow-xs">
      <CardHeader>
        <div className="flex min-w-0 items-center gap-3">
          <ConnectorIcon id={definition.id} />
          <div className="flex min-w-0 flex-col gap-1">
            <CardTitle className="truncate">{name}</CardTitle>
            <CardDescription className="line-clamp-1">{t(`descriptions.${definition.id}`)}</CardDescription>
          </div>
        </div>
        {linked ? (
          <CardAction>
            <ConnectorMenu {...props} />
          </CardAction>
        ) : null}
      </CardHeader>
      <CardContent className="flex-1">
        {linked ? (
          <ConnectorDetails connector={connector} />
        ) : (
          <span className="text-muted-foreground text-sm">
            {definition.auth === "oauth"
              ? t("card.signIn", { provider: definition.provider ?? name })
              : t("card.public")}
          </span>
        )}
      </CardContent>
      <CardFooter>
        {linked ? (
          <SyncButton definition={definition} busy={BUSY_CONNECTOR.has(connector.status)} />
        ) : (
          <Button size="sm" className="w-full" onClick={onConfigure}>
            {t("card.connect")}
          </Button>
        )}
      </CardFooter>
    </Card>
  );
}
