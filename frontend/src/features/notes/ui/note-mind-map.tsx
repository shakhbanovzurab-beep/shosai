import { cn } from "cn";
import { useLocale, useTranslations } from "use-intl";

import { languageDirection } from "@/lib/language";

import { layoutMindMap, NODE_HEIGHT, NODE_WIDTH } from "../domain/mind-map-layout";
import type { MindMapNode } from "../domain/types";

const PADDING = 16;

/**
 * The meeting's topics as a tree growing along the line of text: from the left in a left-to-right interface,
 * mirrored from the right in a right-to-left one. The topics are Leo's words, so each keeps its own direction.
 */
export function NoteMindMap({ root }: { readonly root: MindMapNode }) {
  const t = useTranslations("notesNote");
  // The page may render on the server, where Radix's direction context isn't there: the language says it.
  const rtl = languageDirection(useLocale()) === "rtl";
  const { nodes, edges, width, height } = layoutMindMap(root, rtl);
  const viewWidth = width + PADDING * 2;
  const viewHeight = height + PADDING * 2;

  return (
    <figure className="flex flex-col gap-3">
      <div className="overflow-x-auto rounded-xl border bg-muted/30">
        <svg
          viewBox={`${-PADDING} ${-PADDING} ${viewWidth} ${viewHeight}`}
          width={viewWidth}
          height={viewHeight}
          className="mx-auto block max-w-none"
          role="img"
          aria-labelledby="mind-map-title"
        >
          <title id="mind-map-title">{t("mindMap.title", { topic: root.label })}</title>
          <g className="fill-none stroke-border" strokeWidth={1.5}>
            {edges.map(({ id, path }) => (
              <path key={id} d={path} />
            ))}
          </g>
          {nodes.map((node) => (
            <foreignObject key={node.id} x={node.x} y={node.y} width={NODE_WIDTH} height={NODE_HEIGHT}>
              <div
                className={cn(
                  "flex size-full items-center justify-center rounded-lg px-2 text-center text-xs leading-tight",
                  node.depth === 0 && "bg-primary font-medium text-primary-foreground",
                  node.depth === 1 && "border bg-card font-medium text-card-foreground",
                  node.depth > 1 && "border border-dashed bg-background text-muted-foreground",
                )}
              >
                <span dir="auto" className="line-clamp-2">
                  {node.label}
                </span>
              </div>
            </foreignObject>
          ))}
        </svg>
      </div>
      <figcaption className="text-muted-foreground text-xs">{t("mindMap.caption")}</figcaption>
    </figure>
  );
}
