"use client";

import { SearchX, UserSearch as UserSearchIcon } from "lucide-react";

import { LoadError } from "@/components/feedback";
import { Button } from "@/components/ui/button";
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { errorMessage } from "@/lib/errors";
import { Link } from "@/lib/navigation";

import { formatDate, formatDateTime } from "../domain/format";
import { homeLabel } from "../domain/labels";
import type { UserSearch } from "../domain/search";
import { useUserSearch } from "../model/users";
import { StateBadge } from "./state-badge";

function Hint({ title, description, icon }: { title: string; description: string; icon: React.ReactNode }) {
  return (
    <Empty className="border border-dashed">
      <EmptyHeader>
        <EmptyMedia variant="icon">{icon}</EmptyMedia>
        <EmptyTitle>{title}</EmptyTitle>
        <EmptyDescription>{description}</EmptyDescription>
      </EmptyHeader>
    </Empty>
  );
}

/** Найденные аккаунты; строка ведёт в карточку. */
export function UsersResults({ search, typed }: { search: UserSearch | null; typed: boolean }) {
  const found = useUserSearch(search);

  if (search === null)
    return (
      <Hint
        icon={<UserSearchIcon />}
        title={typed ? "Уточните запрос" : "Кого найти?"}
        description="Почту — целиком, имя — от двух букв. Списка всех людей нет: админка показывает только того, кого ищут."
      />
    );
  if (found.isPending)
    return (
      <div className="flex flex-col gap-2" aria-busy="true">
        <span className="sr-only" role="status">
          Поиск…
        </span>
        <Skeleton className="h-10" />
        <Skeleton className="h-10" />
        <Skeleton className="h-10" />
      </div>
    );
  if (found.isError)
    return (
      <LoadError
        title="Поиск не удался"
        message={errorMessage(found.error) ?? "Сервер не ответил."}
        onRetry={() => void found.refetch()}
        retryLabel="Повторить"
      />
    );
  if (found.users.length === 0)
    return <Hint icon={<SearchX />} title="Никого не нашли" description="Проверьте написание или поищите по имени." />;

  return (
    <div className="flex flex-col gap-3">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Человек</TableHead>
            <TableHead>Состояние</TableHead>
            <TableHead>Дом данных</TableHead>
            <TableHead>Создан</TableHead>
            <TableHead>Последний вход</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {found.users.map((user) => (
            <TableRow key={user.id}>
              <TableCell className="max-w-72">
                <Link href={`/admin/users/${user.id}`} className="block truncate font-medium hover:underline">
                  {user.full_name || user.display_name || user.email}
                </Link>
                <span className="block truncate text-muted-foreground text-xs">{user.email}</span>
              </TableCell>
              <TableCell>
                <StateBadge state={user.state} />
              </TableCell>
              <TableCell>{homeLabel(user.home)}</TableCell>
              <TableCell className="tabular-nums">{formatDate(user.created_at)}</TableCell>
              <TableCell className="tabular-nums">
                {user.last_login_at ? formatDateTime(user.last_login_at) : "ещё не входил"}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      {found.hasNextPage ? (
        <Button
          variant="outline"
          size="sm"
          className="self-center"
          disabled={found.isFetchingNextPage}
          onClick={() => void found.fetchNextPage()}
        >
          {found.isFetchingNextPage ? <Spinner data-icon="inline-start" /> : null}
          Показать ещё
        </Button>
      ) : null}
    </div>
  );
}
