"use client";

import { useRef, useState } from "react";

import { Link2, Search, Upload } from "lucide-react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { InputGroup, InputGroupAddon, InputGroupInput } from "@/components/ui/input-group";
import { Skeleton } from "@/components/ui/skeleton";

import { retry, useMaterials } from "../../model/hooks";
import { uploadFiles } from "../../model/material-actions";
import { useHubWords } from "../../model/words";
import { Block, BlockError, PartialNote, QuietEmpty } from "../shared/block";
import { AddLinkDialog } from "./add-link-dialog";
import { MaterialRow } from "./material-row";

/** The search field appears once there is enough to search through. */
const SEARCH_FROM = 4;

/** Documents and file links of the hub: meeting summaries land here on their own; people add the rest. */
export function MaterialsBlock({ hubId }: { hubId: string }) {
  const t = useTranslations("hubBlocks");
  const words = useHubWords();
  const state = useMaterials(hubId);
  const [query, setQuery] = useState("");
  const [adding, setAdding] = useState(false);
  const picker = useRef<HTMLInputElement>(null);

  let body: React.ReactNode = (
    <div className="flex flex-col gap-2" aria-hidden="true">
      <Skeleton className="h-10 w-full" />
      <Skeleton className="h-10 w-full" />
    </div>
  );
  if (state.status === "error")
    body = <BlockError title={t("materials.loadError")} onRetry={() => void retry.materials(hubId)} />;
  else if (state.status === "ready") {
    const all = state.data.data;
    const needle = query.trim().toLocaleLowerCase();
    const shown = needle ? all.filter((m) => m.title.toLocaleLowerCase().includes(needle)) : all;
    body = (
      <>
        {state.data.partial ? <PartialNote onRetry={() => void retry.materials(hubId)} /> : null}
        {all.length >= SEARCH_FROM ? (
          <InputGroup className="max-w-xs">
            <InputGroupAddon>
              <Search aria-hidden="true" />
            </InputGroupAddon>
            <InputGroupInput
              type="search"
              dir="auto"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={t("materials.find")}
              aria-label={t("materials.find")}
            />
          </InputGroup>
        ) : null}
        {all.length === 0 ? <QuietEmpty>{t("materials.empty")}</QuietEmpty> : null}
        {all.length > 0 && shown.length === 0 ? (
          <p className="text-muted-foreground text-sm">{t("materials.noMatches", { query: query.trim() })}</p>
        ) : null}
        {shown.length > 0 ? (
          <ul className="-mx-2 flex flex-col">
            {shown.map((material) => (
              <MaterialRow key={material.id} hubId={hubId} material={material} />
            ))}
          </ul>
        ) : null}
      </>
    );
  }

  return (
    <Block
      id="materials"
      title={t("materials.title")}
      aside={
        <div className="flex gap-1.5">
          <Button variant="outline" size="xs" className="bg-background" onClick={() => setAdding(true)}>
            <Link2 data-icon="inline-start" aria-hidden="true" />
            {t("materials.addLink")}
          </Button>
          <Button variant="outline" size="xs" className="bg-background" onClick={() => picker.current?.click()}>
            <Upload data-icon="inline-start" aria-hidden="true" />
            {t("materials.upload")}
          </Button>
          <input
            ref={picker}
            type="file"
            multiple
            hidden
            onChange={(event) => {
              const files = [...(event.target.files ?? [])];
              event.target.value = "";
              if (files.length > 0) void uploadFiles(words, hubId, files);
            }}
          />
        </div>
      }
    >
      {body}
      <AddLinkDialog hubId={hubId} open={adding} onOpenChange={setAdding} />
    </Block>
  );
}
