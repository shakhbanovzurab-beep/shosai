"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, FieldContent, FieldGroup, FieldLegend, FieldSet } from "@/components/ui/field";
import { FieldDescription, FieldLabel } from "@/components/ui/field-text";
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Switch } from "@/components/ui/switch";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { LANGUAGES } from "@/lib/language";

import { type BehaviorDefaults, type LanguagePolicy, TONES } from "../domain/contract";
import { useBehavior } from "../model/use-behavior";

const isTone = (value: string): value is BehaviorDefaults["tone"] => TONES.some((tone) => tone.id === value);
const isLanguagePolicy = (value: string): value is LanguagePolicy => value === "user" || value === "fixed";
export function ResponseCard() {
  const { behavior, set } = useBehavior();

  return (
    <Card className="shadow-xs">
      <CardHeader>
        <CardTitle>Ответы по умолчанию</CardTitle>
        <CardDescription>Как Leo отвечает, пока пользователь не изменил это у себя.</CardDescription>
      </CardHeader>
      <CardContent>
        <FieldGroup>
          <FieldSet>
            <FieldLegend variant="label">Стиль ответов</FieldLegend>
            <ToggleGroup
              type="single"
              variant="outline"
              spacing={0}
              value={behavior.tone}
              onValueChange={(value) => (isTone(value) ? set({ tone: value }) : undefined)}
              aria-label="Стиль ответов"
              className="flex-wrap"
            >
              {TONES.map((tone) => (
                <ToggleGroupItem key={tone.id} value={tone.id} className="px-3">
                  {tone.label}
                </ToggleGroupItem>
              ))}
            </ToggleGroup>
          </FieldSet>

          <FieldSet>
            <FieldLegend variant="label">Язык ответов</FieldLegend>
            <RadioGroup
              value={behavior.language_policy}
              onValueChange={(value) => (isLanguagePolicy(value) ? set({ language_policy: value }) : undefined)}
            >
              <Field orientation="horizontal">
                <RadioGroupItem value="user" id="language-user" />
                <FieldLabel htmlFor="language-user" className="font-normal">
                  На языке пользователя — как задан вопрос
                </FieldLabel>
              </Field>
              <Field orientation="horizontal">
                <RadioGroupItem value="fixed" id="language-fixed" />
                <FieldLabel htmlFor="language-fixed" className="font-normal">
                  Всегда на одном языке
                </FieldLabel>
              </Field>
            </RadioGroup>
            <NativeSelect
              aria-label="Фиксированный язык ответов"
              value={behavior.fixed_language}
              onChange={(event) => set({ fixed_language: event.currentTarget.value })}
              disabled={behavior.language_policy !== "fixed"}
              className="w-full sm:w-64"
            >
              {LANGUAGES.map((language) => (
                <NativeSelectOption key={language.code} value={language.code}>
                  {language.label}
                </NativeSelectOption>
              ))}
            </NativeSelect>
          </FieldSet>

          <Field orientation="horizontal">
            <FieldContent>
              <FieldLabel htmlFor="behavior-web-search">Веб-поиск</FieldLabel>
              <FieldDescription>Leo может искать в интернете и ссылаться на источники.</FieldDescription>
            </FieldContent>
            <Switch
              id="behavior-web-search"
              checked={behavior.web_search}
              onCheckedChange={(web_search) => set({ web_search })}
            />
          </Field>
        </FieldGroup>
      </CardContent>
    </Card>
  );
}
