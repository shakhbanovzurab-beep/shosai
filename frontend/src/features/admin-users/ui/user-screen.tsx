"use client";

import { ArrowLeft, SearchX } from "lucide-react";

import { LoadError } from "@/components/feedback";
import { Button } from "@/components/ui/button";
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";
import { isNotFound } from "@/lib/api/errors";
import { errorMessage } from "@/lib/errors";
import { Link } from "@/lib/navigation";

import { useUserCard } from "../model/users";
import { SessionsCard, SignInsCard, SpendCard } from "./user-activity";
import { UserHeader } from "./user-header";

const back = (
  <Button variant="ghost" size="sm" className="-ml-2 w-fit" asChild>
    <Link href="/admin/users">
      <ArrowLeft aria-hidden="true" />
      Поиск пользователей
    </Link>
  </Button>
);

/** Один человек для администратора: кто он, где живут его данные, как он входит и сколько тратит на ИИ. */
export function UserScreen({ id }: { id: string }) {
  const card = useUserCard(id);

  if (card.isPending)
    return (
      <div className="flex flex-col gap-4" aria-busy="true">
        {back}
        <span className="sr-only" role="status">
          Загрузка карточки…
        </span>
        <Skeleton className="h-40 rounded-xl" />
        <Skeleton className="h-64 rounded-xl" />
      </div>
    );

  if (card.isError)
    return (
      <div className="flex flex-col gap-4">
        {back}
        {isNotFound(card.error) ? (
          <Empty className="border border-dashed">
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <SearchX />
              </EmptyMedia>
              <EmptyTitle>Пользователь не найден</EmptyTitle>
              <EmptyDescription>Аккаунт удалён или ссылка неверна.</EmptyDescription>
            </EmptyHeader>
          </Empty>
        ) : (
          <LoadError
            title="Не удалось открыть карточку"
            message={errorMessage(card.error) ?? "Сервер не ответил."}
            onRetry={() => void card.refetch()}
            retryLabel="Повторить"
          />
        )}
      </div>
    );

  return (
    <div className="flex flex-col gap-4">
      {back}
      <UserHeader card={card.data} />
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="flex min-w-0 flex-col gap-4">
          <SessionsCard sessions={card.data.sessions} />
          <SignInsCard signIns={card.data.sign_ins} />
        </div>
        <SpendCard spend={card.data.spend} />
      </div>
    </div>
  );
}
