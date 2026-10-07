"use client";

import Link from "next/link";

import { FileText, FileX, Link2, X } from "lucide-react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";

import type { Material } from "../../domain/contract";
import { removeMaterial } from "../../model/material-actions";
import { useHubWords } from "../../model/words";
import { useHubPhrases } from "../shared/phrases";

const HOVER_ONLY =
  "[@media(hover:hover)]:opacity-0 group-hover/material:opacity-100 group-focus-within/material:opacity-100 motion-safe:transition-opacity";

/** Its icon: a document, a file link, or one whose source is gone. */
function MaterialIcon({ material }: { material: Material }) {
  const className = "size-4 shrink-0 text-muted-foreground";
  if (material.gone) return <FileX className={className} aria-hidden="true" />;
  if (material.kind === "document") return <FileText className={className} aria-hidden="true" />;
  return <Link2 className={className} aria-hidden="true" />;
}

/** One material: where it came from, and a way to take it out of the hub. A deleted source says so instead of failing. */
export function MaterialRow({ hubId, material }: { hubId: string; material: Material }) {
  const t = useTranslations("hubBlocks");
  const words = useHubWords();
  const say = useHubPhrases();
  const external = material.url?.startsWith("http") ?? false;
  return (
    <li className="group/material flex items-center gap-3 rounded-lg px-2 py-2 hover:bg-muted/40">
      <MaterialIcon material={material} />
      <div className="flex min-w-0 flex-1 flex-col">
        {material.url && !material.gone ? (
          <Link
            href={material.url}
            dir="auto"
            className="truncate text-sm underline-offset-4 hover:underline"
            {...(external ? { target: "_blank", rel: "noreferrer" } : {})}
          >
            {material.title}
          </Link>
        ) : (
          <span dir="auto" className={material.gone ? "truncate text-muted-foreground text-sm" : "truncate text-sm"}>
            {material.title}
          </span>
        )}
        <span className="truncate text-muted-foreground text-xs">
          {material.gone
            ? t("materials.gone")
            : t("materials.origin", {
                source: material.sessionId ? "meeting" : "hand",
                date: say.date(material.addedAt),
              })}
        </span>
      </div>
      <Button
        variant="ghost"
        size="icon-xs"
        className={`shrink-0 border-transparent bg-transparent text-muted-foreground ${HOVER_ONLY}`}
        aria-label={t("materials.removeLabel", { title: material.title })}
        onClick={() => void removeMaterial(words, hubId, material)}
      >
        <X />
      </Button>
    </li>
  );
}
