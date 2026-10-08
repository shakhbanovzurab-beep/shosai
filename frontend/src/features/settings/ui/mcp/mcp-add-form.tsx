"use client";

import { useActionState } from "react";

import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";

import type { McpTransport } from "../../domain/mcp-contract";
import { MCP_TRANSPORT_NAMES } from "../../domain/names";
import { addMcpServer } from "../../model/mcp-actions";

const TRANSPORTS = Object.keys(MCP_TRANSPORT_NAMES) as McpTransport[];

/** Adds a remote MCP server; the auth header is sent once and never shown again. */
export function McpAddForm({ onDone }: { onDone: () => void }) {
  const t = useTranslations("settingsMcp");
  const common = useTranslations("common");
  const [error, submit, pending] = useActionState(async (_prev: string | null, form: FormData) => {
    const field = (key: string) => String(form.get(key) ?? "").trim();
    const failure = await addMcpServer(
      {
        name: field("name"),
        url: field("url"),
        transport: field("transport") === "sse" ? "sse" : ("streamable_http" satisfies McpTransport),
        auth_header: field("auth_header"),
      },
      t,
    );
    if (failure === null) onDone();
    return failure;
  }, null);

  return (
    <form action={submit} className="flex flex-col gap-4 rounded-xl border p-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="flex flex-col gap-2">
          <Label htmlFor="mcp-name">{common("fields.name")}</Label>
          {/* i18n-ignore: an example service's name, the same in every language */}
          <Input id="mcp-name" name="name" dir="auto" required placeholder="Linear" />
        </div>
        <div className="flex flex-col gap-2">
          <Label htmlFor="mcp-transport">{t("form.transport")}</Label>
          <Select name="transport" defaultValue="streamable_http">
            <SelectTrigger id="mcp-transport" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                {TRANSPORTS.map((transport) => (
                  <SelectItem key={transport} value={transport}>
                    {MCP_TRANSPORT_NAMES[transport].full}
                  </SelectItem>
                ))}
              </SelectGroup>
            </SelectContent>
          </Select>
        </div>
      </div>
      <div className="flex flex-col gap-2">
        <Label htmlFor="mcp-url">{t("form.url")}</Label>
        {/* i18n-ignore: an example URL, written the same in every language */}
        <Input id="mcp-url" name="url" type="url" dir="auto" required placeholder="https://mcp.example.com/mcp" />
      </div>
      <div className="flex flex-col gap-2">
        <Label htmlFor="mcp-auth">
          {t.rich("form.auth", {
            optional: (chunks) => <span className="font-normal text-muted-foreground">{chunks}</span>,
          })}
        </Label>
        {/* i18n-ignore: “Bearer” is the HTTP authorization scheme, never translated */}
        <Input id="mcp-auth" name="auth_header" type="password" dir="auto" autoComplete="off" placeholder="Bearer …" />
      </div>
      {error ? (
        <p role="alert" className="text-destructive text-sm">
          {error}
        </p>
      ) : null}
      <div className="flex justify-end gap-2">
        <Button type="button" variant="ghost" onClick={onDone}>
          {common("actions.cancel")}
        </Button>
        <Button type="submit" disabled={pending}>
          {pending ? <Spinner data-icon="inline-start" /> : null}
          {t("add")}
        </Button>
      </div>
    </form>
  );
}
