"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";

import { FEATURE_PROMPT_MAX, FEATURE_TOKENS, FEATURES, type FeatureId, type FeaturePrompt } from "../domain/contract";
import { usePlatformPrompts } from "../model/platform-prompts-provider";
import { PromptField } from "./prompt-field";

function FeatureCard({ id, label, description }: { id: FeatureId; label: string; description: string }) {
  const {
    state: { config },
    actions: { update },
  } = usePlatformPrompts();
  const prompt = config.features[id];
  const change = (patch: Partial<FeaturePrompt>) =>
    update((current) => ({
      ...current,
      features: { ...current.features, [id]: { ...current.features[id], ...patch } },
    }));

  return (
    <Card className="shadow-xs">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          {label}
          {prompt.enabled ? null : <Badge variant="outline">Выключен</Badge>}
        </CardTitle>
        <CardDescription>{description}</CardDescription>
        <CardAction>
          <Switch
            checked={prompt.enabled}
            onCheckedChange={(enabled) => change({ enabled })}
            aria-label={`Промт функции «${label}» включён`}
          />
        </CardAction>
      </CardHeader>
      <CardContent className="flex flex-col gap-2">
        <PromptField
          id={`feature-${id}`}
          label={`Промт функции «${label}»`}
          value={prompt.content}
          onChange={(content) => change({ content })}
          maxChars={FEATURE_PROMPT_MAX}
          tokenBudget={FEATURE_TOKENS}
          placeholder="For example: Lead with the decisions, then the tasks with their owners."
          className={prompt.enabled ? "min-h-32" : "min-h-32 text-muted-foreground"}
        />
        {prompt.enabled ? null : (
          <p className="text-muted-foreground text-xs">Пока выключено, функция работает без дополнения оператора.</p>
        )}
      </CardContent>
    </Card>
  );
}

/** Дополнения оператора к промтам функций, у которых свой вызов модели. */
export function FeaturesSection() {
  return (
    <div className="grid gap-4 xl:grid-cols-2">
      {FEATURES.map((feature) => (
        <FeatureCard key={feature.id} id={feature.id} label={feature.label} description={feature.description} />
      ))}
    </div>
  );
}
