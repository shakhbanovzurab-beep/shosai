"use client";

import { useEffect, useRef, useState } from "react";

import { CircleSlash } from "lucide-react";
import { useTranslations } from "use-intl";

import { LoadError } from "@/components/feedback";
import { useDirection } from "@/components/ui/direction";
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { isNotFound } from "@/lib/api/errors";
import { lazyComponent } from "@/lib/lazy-component";

import { taskResource, useTaskDetail } from "../../model/task-resource";
import { closeTask, useOpenTaskId } from "./task-address";

function Loading() {
  const t = useTranslations("kanbanPanel");
  return (
    <div className="flex flex-col gap-4" role="status">
      <span className="sr-only">{t("states.loading")}</span>
      <Skeleton className="h-8 w-3/4" />
      <Skeleton className="h-24 w-full" />
      <Skeleton className="h-40 w-full" />
    </div>
  );
}

function Gone() {
  const t = useTranslations("kanbanPanel");
  return (
    <Empty>
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <CircleSlash />
        </EmptyMedia>
        <EmptyTitle>{t("states.gone")}</EmptyTitle>
        <EmptyDescription>{t("states.goneHint")}</EmptyDescription>
      </EmptyHeader>
    </Empty>
  );
}

// Тело панели — отдельный кусок: доске для первой отрисовки оно не нужно. Браузер берёт его в простое после
// доски, поэтому первое открытие карточки не ждёт загрузки.
const loadPanelBody = () => import("./panel-body").then((module) => module.PanelBody);
const PanelBody = lazyComponent(loadPanelBody, { loading: () => <Loading /> });

function usePreloadedPanel() {
  useEffect(() => {
    const preload = () => void loadPanelBody();
    if ("requestIdleCallback" in window) {
      const id = window.requestIdleCallback(preload, { timeout: 3000 });
      return () => window.cancelIdleCallback(id);
    }
    const timer = setTimeout(preload, 1500);
    return () => clearTimeout(timer);
  }, []);
}

/** Задача по id: загрузка, «задачи больше нет», сбой с повтором — или её тело. */
function PanelContent({ taskId }: { taskId: string }) {
  const t = useTranslations("kanbanPanel");
  const tc = useTranslations("common");
  const state = useTaskDetail(taskId);
  if (state.status === "loading") return <Loading />;
  if (state.status === "error")
    return isNotFound(state.cause) ? (
      <Gone />
    ) : (
      <LoadError
        title={t("states.failed")}
        message={state.message}
        retryLabel={tc("actions.retry")}
        onRetry={() => void taskResource(taskId).refresh()}
      />
    );
  return <PanelBody detail={state.data} />;
}

/**
 * Панель задачи поверх доски: сбоку на компьютере, на весь экран на телефоне; с конца строки — справа, а в
 * арабском слева. Она не модальная, как панели задач в трекерах: доска за ней живая — щелчок по другой карточке
 * открывает её здесь же, тосты с Undo нажимаются, а клики мимо панель не закрывают. Закрывают крестик, Esc внутри
 * панели и «Назад»; фокус возвращается к карточке.
 */
export function TaskPanel() {
  const taskId = useOpenTaskId();
  const t = useTranslations("kanbanPanel");
  // Последняя открытая остаётся на экране, пока панель уезжает, и к её карточке возвращается фокус.
  const [shown, setShown] = useState(taskId);
  if (taskId !== null && taskId !== shown) setShown(taskId);
  const side = useDirection() === "rtl" ? "left" : "right";
  const contentRef = useRef<HTMLDivElement>(null);
  usePreloadedPanel();
  return (
    <Sheet modal={false} open={taskId !== null} onOpenChange={(open) => (open ? undefined : closeTask())}>
      <SheetContent
        ref={contentRef}
        side={side}
        onInteractOutside={(event) => event.preventDefault()}
        // Esc на доске — её дело (например, отмена перетаскивания); панель закрывает только Esc внутри неё.
        onEscapeKeyDown={(event) => {
          if (!contentRef.current?.contains(document.activeElement)) event.preventDefault();
        }}
        aria-describedby={undefined}
        className="w-full gap-0 overflow-y-auto overscroll-contain p-5 data-[side=left]:w-full data-[side=right]:w-full sm:p-6 data-[side=left]:sm:max-w-2xl data-[side=right]:sm:max-w-2xl"
        onCloseAutoFocus={(event) => {
          const card = shown ? document.querySelector<HTMLElement>(`[data-task-id="${CSS.escape(shown)}"]`) : null;
          if (!card) return;
          event.preventDefault();
          card.focus();
        }}
      >
        <SheetTitle className="sr-only">{t("titleLabel")}</SheetTitle>
        {shown ? <PanelContent taskId={shown} /> : null}
      </SheetContent>
    </Sheet>
  );
}
