"use client";

import { Search } from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { InputGroup, InputGroupAddon, InputGroupInput } from "@/components/ui/input-group";
import { useRouter } from "@/lib/navigation";

import { userSearchOf } from "../domain/search";
import { UsersResults } from "./users-results";

/**
 * Пользователи для администратора: найти человека по почте или имени и открыть его карточку. Запрос живёт в
 * адресе (`?q=`), поэтому «назад» из карточки возвращает к тем же результатам.
 */
export function UsersScreen({ query }: { query: string }) {
  const router = useRouter();
  const search = userSearchOf(query);

  function submit(form: FormData) {
    const text = String(form.get("q") ?? "").trim();
    router.replace(text ? `/admin/users?q=${encodeURIComponent(text)}` : "/admin/users");
  }

  return (
    <Card>
      <CardHeader className="border-b">
        <CardTitle className="text-xl leading-none">Пользователи</CardTitle>
        <CardDescription>Найдите человека по почте или имени: оба дома данных, новые аккаунты первыми.</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <search className="max-w-xl">
          <form action={submit}>
            <InputGroup>
              <InputGroupAddon>
                <Search aria-hidden="true" />
              </InputGroupAddon>
              <InputGroupInput
                key={query}
                name="q"
                type="search"
                defaultValue={query}
                aria-label="Почта или имя"
                placeholder="ivan@example.com или Иван…"
                autoComplete="off"
                spellCheck={false}
                maxLength={254}
              />
            </InputGroup>
          </form>
        </search>
        <UsersResults search={search} typed={query.trim().length > 0} />
      </CardContent>
    </Card>
  );
}
