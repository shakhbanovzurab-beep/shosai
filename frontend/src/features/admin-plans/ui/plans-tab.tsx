"use client";

import { useState } from "react";

import { Layers, Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { usePollingResource } from "@/hooks/use-polling-resource";
import { pluralizeRu } from "@/lib/plural";

import type { Plan, PromoCode } from "../domain/contract";
import { formatInteger } from "../domain/format";
import { removePlan } from "../model/plan-actions";
import { plansResource, promosResource } from "../model/plans-store";
import { ConfirmDialog } from "./confirm-dialog";
import { PlanForm } from "./plan-form";
import { PlansTable } from "./plans-table";
import { ResourceView } from "./resource-state";

/** `plan: null` creates a new plan. */
type Editing = { plan: Plan | null } | null;

function RemovePlanText({ plan, promos }: { plan: Plan; promos: PromoCode[] | null }) {
  if (plan.subscribers > 0) {
    const count = `${formatInteger(plan.subscribers)} ${pluralizeRu(plan.subscribers, ["подписчик", "подписчика", "подписчиков"])}`;
    return (
      <>
        <span>
          У тарифа {count}, поэтому удалить его нельзя — он будет перенесён в архив. Действующие подписки сохранятся, но
          купить тариф станет нельзя.
        </span>
        <span>Промокоды, привязанные только к этому тарифу, перестанут применяться — они будут отмечены в списке.</span>
      </>
    );
  }
  const scoped = promos?.filter((promo) => promo.plan_ids.includes(plan.id)) ?? [];
  const orphaned = scoped.filter((promo) => promo.plan_ids.length === 1);
  return (
    <>
      <span>Подписчиков у тарифа нет, он будет удалён без возможности восстановления.</span>
      {scoped.length > 0 ? (
        <span>
          Тариф будет убран из промокодов: {scoped.map((promo) => promo.code).join(", ")}.
          {orphaned.length > 0
            ? ` ${orphaned.map((promo) => promo.code).join(", ")} останутся без тарифов и будут отключены.`
            : null}
        </span>
      ) : null}
    </>
  );
}

export function PlansTab() {
  const state = usePollingResource(plansResource);
  const promos = usePollingResource(promosResource);
  const [showArchived, setShowArchived] = useState(false);
  const [editing, setEditing] = useState<Editing>(null);
  const [removing, setRemoving] = useState<Plan | null>(null);

  const close = () => setEditing(null);

  return (
    <div className="flex flex-col gap-4">
      <ResourceView state={state} errorTitle="Не удалось загрузить тарифы" onRetry={() => void plansResource.refresh()}>
        {({ plans }) => {
          const archived = plans.filter((plan) => plan.archived).length;
          const visible = showArchived ? plans : plans.filter((plan) => !plan.archived);
          return (
            <>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-muted-foreground text-sm">
                  <span>
                    {plans.length - archived} {pluralizeRu(plans.length - archived, ["тариф", "тарифа", "тарифов"])}
                    {archived > 0 ? `, ${archived} в архиве` : ""}
                  </span>
                  {archived > 0 ? (
                    <div className="flex items-center gap-2">
                      <Switch id="plans-show-archived" checked={showArchived} onCheckedChange={setShowArchived} />
                      <Label htmlFor="plans-show-archived" className="font-normal">
                        Показывать архивные
                      </Label>
                    </div>
                  ) : null}
                </div>
                <Button size="sm" onClick={() => setEditing({ plan: null })}>
                  <Plus data-icon="inline-start" />
                  Новый тариф
                </Button>
              </div>
              {visible.length > 0 ? (
                <PlansTable plans={visible} onEdit={(plan) => setEditing({ plan })} onRemove={setRemoving} />
              ) : (
                <Empty className="border border-dashed">
                  <EmptyHeader>
                    <EmptyMedia variant="icon">
                      <Layers />
                    </EmptyMedia>
                    <EmptyTitle>Тарифов пока нет</EmptyTitle>
                    <EmptyDescription>
                      Создайте первый тариф — он появится на странице оплаты и в приложениях.
                    </EmptyDescription>
                  </EmptyHeader>
                  <EmptyContent>
                    <Button size="sm" onClick={() => setEditing({ plan: null })}>
                      <Plus data-icon="inline-start" />
                      Новый тариф
                    </Button>
                  </EmptyContent>
                </Empty>
              )}
            </>
          );
        }}
      </ResourceView>

      <Dialog open={editing !== null} onOpenChange={(open) => (open ? undefined : close())}>
        <DialogContent className="max-h-[calc(100dvh-2rem)] overflow-y-auto sm:max-w-2xl" showCloseButton={false}>
          <DialogHeader>
            <DialogTitle>{editing?.plan ? `Тариф «${editing.plan.name}»` : "Новый тариф"}</DialogTitle>
            <DialogDescription>
              Цены указываются в рублях. Изменения цены действуют для новых оплат и продлений.
            </DialogDescription>
          </DialogHeader>
          {editing ? <PlanForm key={editing.plan?.id ?? "new"} plan={editing.plan} onDone={close} /> : null}
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={removing !== null}
        title={
          removing && removing.subscribers > 0
            ? `Перенести «${removing.name}» в архив?`
            : `Удалить тариф «${removing?.name ?? ""}»?`
        }
        confirmLabel={removing && removing.subscribers > 0 ? "В архив" : "Удалить"}
        destructive
        onConfirm={() => (removing ? removePlan(removing) : Promise.resolve(true))}
        onClose={() => setRemoving(null)}
      >
        {removing ? (
          <RemovePlanText plan={removing} promos={promos.status === "ready" ? promos.data.promo_codes : null} />
        ) : null}
      </ConfirmDialog>
    </div>
  );
}
