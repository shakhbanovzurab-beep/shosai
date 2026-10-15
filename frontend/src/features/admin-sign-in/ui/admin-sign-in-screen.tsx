"use client";

import { useActionState } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field, FieldGroup } from "@/components/ui/field";
import { FieldError, FieldLabel } from "@/components/ui/field-text";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { Wordmark } from "@/features/identity/ui/wordmark";
import { useRouter } from "@/lib/navigation";

import { ADMIN_HOME } from "../domain/login-path";
import { signIn } from "../model/admin-session";

interface Attempt {
  problem: string | null;
  // React сбрасывает форму после действия: логин возвращается в поле отсюда, пароль вводится заново.
  username: string;
}

const FIRST: Attempt = { problem: null, username: "" };

/** Вход единственного администратора: логин и пароль из окружения сервера (ADR 0049). */
export function AdminSignInScreen() {
  const router = useRouter();
  const [attempt, submit, pending] = useActionState(async (_previous: Attempt, form: FormData): Promise<Attempt> => {
    const username = String(form.get("username") ?? "").trim();
    const problem = await signIn(username, String(form.get("password") ?? ""));
    if (problem === null) router.replace(ADMIN_HOME);
    return { problem, username };
  }, FIRST);

  return (
    <main className="flex min-h-dvh items-center justify-center bg-muted/40 px-4 py-12">
      <div className="flex w-full max-w-sm flex-col items-center gap-6">
        <Wordmark />
        <Card className="w-full gap-0 px-6 py-7 shadow-sm sm:px-8">
          <h1 className="mb-5 text-center font-semibold text-lg tracking-tight">Вход в админку</h1>
          <form action={submit} className="flex flex-col gap-4">
            <FieldGroup>
              <Field>
                <FieldLabel htmlFor="admin-username">Логин</FieldLabel>
                <Input
                  id="admin-username"
                  name="username"
                  autoComplete="username"
                  autoCapitalize="none"
                  spellCheck={false}
                  defaultValue={attempt.username}
                  required
                  maxLength={64}
                  className="h-11"
                />
              </Field>
              <Field>
                <FieldLabel htmlFor="admin-password">Пароль</FieldLabel>
                <Input
                  id="admin-password"
                  name="password"
                  type="password"
                  autoComplete="current-password"
                  required
                  maxLength={256}
                  className="h-11"
                />
              </Field>
              {attempt.problem ? <FieldError role="alert">{attempt.problem}</FieldError> : null}
            </FieldGroup>
            <Button type="submit" size="lg" className="h-11" disabled={pending}>
              {pending ? <Spinner data-icon="inline-start" /> : null}
              Войти
            </Button>
          </form>
        </Card>
      </div>
    </main>
  );
}
