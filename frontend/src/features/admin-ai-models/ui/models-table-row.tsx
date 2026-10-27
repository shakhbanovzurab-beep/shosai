"use client";

import { Archive, Star } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { TableCell, TableRow } from "@/components/ui/table";

import type { AiModel } from "../domain/contract";
import { formatCompact, formatInteger, formatPrice, formatUsd } from "../domain/format";
import { switchModel } from "../model/ai-models-store";
import { decideTier, retireModel } from "../model/catalogue-actions";

const TIER_NAMES = { standard: "стандартный", frontier: "frontier" } as const;

const price = (value: number | null) => (value === null ? "—" : formatPrice(value));

/** Строка каталога; `held` — модель держит умолчание или запасная модель роли. */
export function ModelRow({ model, held }: { model: AiModel; held: boolean }) {
  return (
    <TableRow data-disabled={model.enabled ? undefined : ""} className="group">
      <TableCell className="max-w-80 py-3">
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <span className="truncate font-medium group-data-disabled:text-muted-foreground">{model.name}</span>
          {model.is_default ? (
            <Badge variant="secondary">
              <Star aria-hidden="true" />
              Leo по умолчанию
            </Badge>
          ) : null}
          {model.tier === "frontier" ? <Badge variant="outline">Frontier</Badge> : null}
        </div>
        <div className="truncate font-mono text-muted-foreground text-xs">{model.openrouter_id}</div>
        {model.tier_proposed ? <TierProposal model={model} proposed={model.tier_proposed} /> : null}
      </TableCell>
      <TableCell className="text-muted-foreground">{model.provider}</TableCell>
      <TableCell className="text-right tabular-nums">{formatCompact(model.context_length)}</TableCell>
      <TableCell className="text-right tabular-nums">{price(model.price_input_per_m)}</TableCell>
      <TableCell className="text-right tabular-nums">{price(model.price_output_per_m)}</TableCell>
      <TableCell className="text-right tabular-nums">{formatUsd(model.month_spend)}</TableCell>
      <TableCell className="text-right text-muted-foreground tabular-nums">
        {formatInteger(model.month_requests)}
      </TableCell>
      <TableCell className="text-right">
        <div className="flex items-center justify-end gap-1">
          {model.enabled || held ? null : (
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={() => void retireModel(model.id)}
              aria-label={`Убрать модель ${model.name} из каталога`}
              title="Убрать из каталога"
            >
              <Archive aria-hidden="true" />
            </Button>
          )}
          <Switch
            checked={model.enabled}
            disabled={held}
            onCheckedChange={(checked) => void switchModel(model.id, checked)}
            aria-label={`Модель ${model.name} доступна пользователям`}
            title={held ? "Модель — умолчание роли: её нельзя выключить" : undefined}
          />
        </div>
      </TableCell>
    </TableRow>
  );
}

function TierProposal({ model, proposed }: { model: AiModel; proposed: AiModel["tier"] }) {
  return (
    <div className="mt-1.5 flex flex-wrap items-center gap-2 text-xs">
      <span className="text-amber-700 dark:text-amber-300">
        Цена предлагает уровень {TIER_NAMES[proposed]} вместо {TIER_NAMES[model.tier]}
      </span>
      <Button size="xs" variant="outline" onClick={() => void decideTier(model.id, "confirm")}>
        Подтвердить
      </Button>
      <Button size="xs" variant="ghost" onClick={() => void decideTier(model.id, "decline")}>
        Отклонить
      </Button>
    </div>
  );
}
