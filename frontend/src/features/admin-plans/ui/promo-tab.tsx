"use client";

import { useState } from "react";

import { Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { usePollingResource } from "@/hooks/use-polling-resource";

import type { Plan, PromoCode } from "../domain/contract";
import { formatInteger } from "../domain/format";
import type { PromoFormTarget } from "../domain/promo-form-values";
import { plansResource, promosResource } from "../model/plans-store";
import { removePromo } from "../model/promo-actions";
import { ConfirmDialog } from "./confirm-dialog";
import { PromoForm } from "./promo-form";
import { PromoList } from "./promo-list";
import { ResourceView } from "./resource-state";

const EMPTY_PLANS: Plan[] = [];

function dialogTitle(target: PromoFormTarget | null) {
  if (target?.mode === "edit") return `Промокод ${target.promo.code}`;
  if (target?.mode === "copy") return `Копия ${target.promo.code}`;
  return "Новый промокод";
}

export function PromoTab() {
  const promos = usePollingResource(promosResource);
  const plans = usePollingResource(plansResource);
  const [target, setTarget] = useState<PromoFormTarget | null>(null);
  const [removing, setRemoving] = useState<PromoCode | null>(null);

  const plansReady = plans.status === "ready";
  const planList = plansReady ? plans.data.plans : EMPTY_PLANS;
  const create = () => setTarget({ mode: "create" });
  const close = () => setTarget(null);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-muted-foreground text-sm">
          Скидки при оплате тарифов в приложениях Leo и на сайте. Код вводится при оформлении подписки.
        </p>
        <Button size="sm" onClick={create} disabled={!plansReady}>
          <Plus data-icon="inline-start" />
          Новый промокод
        </Button>
      </div>

      <ResourceView
        state={promos}
        errorTitle="Не удалось загрузить промокоды"
        onRetry={() => void promosResource.refresh()}
      >
        {({ promo_codes }) => (
          <PromoList
            promos={promo_codes}
            plans={planList}
            onCreate={create}
            onEdit={(promo) => setTarget({ mode: "edit", promo })}
            onCopy={(promo) => setTarget({ mode: "copy", promo })}
            onRemove={setRemoving}
          />
        )}
      </ResourceView>

      <Dialog open={target !== null && plansReady} onOpenChange={(open) => (open ? undefined : close())}>
        <DialogContent className="max-h-[calc(100dvh-2rem)] overflow-y-auto sm:max-w-2xl" showCloseButton={false}>
          <DialogHeader>
            <DialogTitle>{dialogTitle(target)}</DialogTitle>
            <DialogDescription>
              {target?.mode === "edit"
                ? `Использован ${formatInteger(target.promo.redemptions)} раз. Изменения действуют для новых оплат.`
                : "Скидка применяется к цене тарифа при оплате."}
            </DialogDescription>
          </DialogHeader>
          {target ? (
            <PromoForm
              key={target.mode === "create" ? "new" : `${target.mode}-${target.promo.id}`}
              target={target}
              plans={planList}
              onDone={close}
            />
          ) : null}
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={removing !== null}
        title={`Удалить промокод ${removing?.code ?? ""}?`}
        confirmLabel="Удалить"
        destructive
        onConfirm={() => (removing ? removePromo(removing) : Promise.resolve(true))}
        onClose={() => setRemoving(null)}
      >
        <span>
          Код перестанет приниматься при оплате. Скидки, которые уже получили пользователи, сохранятся. Чтобы временно
          остановить код, лучше отключить его.
        </span>
      </ConfirmDialog>
    </div>
  );
}
