"use client";

import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

import type { AiModel, RoleDefault } from "../domain/contract";
import { candidatesFor, defaultOf, ROLES } from "../domain/roles";
import { setRoleDefault } from "../model/ai-models-store";

const NONE = "";

/** Умолчание и запасная модель каждой роли: отвечают, когда человек не выбрал модель или его выбор не может. */
export function DefaultsCard({ models, defaults }: { models: AiModel[]; defaults: RoleDefault[] }) {
  return (
    <Card>
      <CardHeader className="border-b">
        <CardTitle className="font-normal">Модели по умолчанию</CardTitle>
        <CardDescription>
          Отвечают в роли, когда человек не выбрал свою модель или его выбор недоступен на тарифе. Запасная модель
          отвечает, если основная не может.
        </CardDescription>
      </CardHeader>
      <CardContent className="px-0">
        <Table className="[&_td:first-child]:pl-4 [&_td:last-child]:pr-4 [&_th:first-child]:pl-4 [&_th:last-child]:pr-4">
          <TableHeader className="[&_tr]:border-border/50">
            <TableRow className="hover:bg-transparent">
              <TableHead className="h-10 font-normal text-muted-foreground">Роль</TableHead>
              <TableHead className="h-10 font-normal text-muted-foreground">По умолчанию</TableHead>
              <TableHead className="h-10 font-normal text-muted-foreground">Запасная</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody className="[&_tr]:border-border/50">
            {ROLES.map((role) => (
              <RoleRow
                key={role.id}
                role={role}
                candidates={candidatesFor(models, role.vision)}
                current={defaultOf(defaults, role.id)}
              />
            ))}
          </TableBody>
        </Table>
      </CardContent>
      <CardFooter className="text-muted-foreground text-xs">
        Умолчание — включённая стандартная модель, которая умеет нужное роли; Leo и скриншотам нужны картинки.
      </CardFooter>
    </Card>
  );
}

function RoleRow({
  role,
  candidates,
  current,
}: {
  role: (typeof ROLES)[number];
  candidates: AiModel[];
  current: RoleDefault | undefined;
}) {
  const fallbacks = candidates.filter((model) => model.id !== current?.model_id);
  return (
    <TableRow className="hover:bg-transparent">
      <TableCell className="py-2">{role.label}</TableCell>
      <TableCell className="py-2">
        <NativeSelect
          aria-label={`Модель по умолчанию: ${role.label}`}
          value={current?.model_id ?? NONE}
          onChange={(event) => {
            const chosen = event.currentTarget.value;
            const fallback = current?.fallback_model_id === chosen ? null : (current?.fallback_model_id ?? null);
            if (chosen) void setRoleDefault(role.id, chosen, fallback);
          }}
          disabled={candidates.length === 0}
          className="w-full sm:w-64"
        >
          {current ? null : <NativeSelectOption value={NONE}>Не выбрана</NativeSelectOption>}
          {candidates.map((model) => (
            <NativeSelectOption key={model.id} value={model.id}>
              {model.name}
            </NativeSelectOption>
          ))}
        </NativeSelect>
      </TableCell>
      <TableCell className="py-2">
        <NativeSelect
          aria-label={`Запасная модель: ${role.label}`}
          value={current?.fallback_model_id ?? NONE}
          onChange={(event) =>
            current ? void setRoleDefault(role.id, current.model_id, event.currentTarget.value || null) : undefined
          }
          disabled={current === undefined}
          className="w-full sm:w-64"
        >
          <NativeSelectOption value={NONE}>Нет</NativeSelectOption>
          {fallbacks.map((model) => (
            <NativeSelectOption key={model.id} value={model.id}>
              {model.name}
            </NativeSelectOption>
          ))}
        </NativeSelect>
      </TableCell>
    </TableRow>
  );
}
