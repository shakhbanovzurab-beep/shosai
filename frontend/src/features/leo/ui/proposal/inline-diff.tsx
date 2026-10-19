"use client";

import { cn } from "cn";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { CardContent } from "@/components/ui/card";

import { changeIndexes, type DiffSegment, segmentKeys } from "../../domain/proposals";

function TakenChange({ remove, insert }: { remove: string; insert: string }) {
  return (
    <>
      {remove ? (
        <del className="rounded-sm bg-destructive/10 box-decoration-clone px-0.5 text-destructive">{remove}</del>
      ) : null}
      {insert ? (
        <ins
          className={cn(
            "rounded-sm bg-emerald-500/15 box-decoration-clone px-0.5 text-emerald-700 no-underline dark:text-emerald-300",
            remove && "ms-0.5",
          )}
        >
          {insert}
        </ins>
      ) : null}
    </>
  );
}

type InlineDiffProps = {
  target: string;
  segments: DiffSegment[];
  /** Номера принятых замен; решение держит карточка и отправляет с «Применить». */
  accepted: ReadonlySet<number>;
  onToggle: (index: number) => void;
  onAll: (take: boolean) => void;
};

/**
 * Правки Leo прямо в тексте: убранное зачёркнуто (`del`), новое подчёркнуто цветом (`ins`). Каждая замена —
 * флажок: нажатие берёт её или возвращает исходные слова. Цвет — не единственный признак: есть зачёркивание.
 */
export function InlineDiff({ target, segments, accepted, onToggle, onAll }: InlineDiffProps) {
  const t = useTranslations("leoCards");
  const total = changeIndexes(segments).length;
  const keys = segmentKeys(segments);

  return (
    <CardContent className="flex flex-col gap-3">
      <p className="text-muted-foreground text-xs">{t("diff.label", { target })}</p>
      <p dir="auto" className="rounded-lg border bg-muted/30 px-3 py-2 text-sm leading-7">
        {segments.map((segment, index) => {
          const key = keys[index];
          if (segment.type === "equal") return <span key={key}>{segment.text}</span>;
          const taken = accepted.has(index);
          return (
            // Правка — подпись к скрытому флажку: строчный элемент переносится как текст, а не блоком, как кнопка.
            <label
              key={key}
              className="relative cursor-pointer rounded-sm has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring"
            >
              <input
                type="checkbox"
                className="sr-only"
                checked={taken}
                aria-label={t("diff.toggle", { remove: segment.remove, insert: segment.insert })}
                onChange={() => onToggle(index)}
              />
              {taken ? <TakenChange remove={segment.remove} insert={segment.insert} /> : null}
              {taken ? null : (
                // Не взятая правка: исходные слова с пунктирной подсказкой; у чистой вставки — значок, чтобы её вернуть.
                <span className="rounded-sm underline decoration-muted-foreground/60 decoration-dotted underline-offset-4">
                  {segment.remove || <span className="px-1 text-muted-foreground">+</span>}
                </span>
              )}
            </label>
          );
        })}
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <span className="me-auto text-muted-foreground text-xs tabular-nums">
          {t("diff.selected", { selected: accepted.size, total })}
        </span>
        <Button variant="ghost" size="xs" onClick={() => onAll(false)}>
          {t("diff.none")}
        </Button>
        <Button variant="ghost" size="xs" onClick={() => onAll(true)}>
          {t("diff.all")}
        </Button>
      </div>
    </CardContent>
  );
}
