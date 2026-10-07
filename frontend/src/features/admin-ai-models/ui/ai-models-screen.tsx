import { AiModelsView } from "./ai-models-view";

export function AiModelsScreen() {
  return (
    <div className="flex flex-col gap-4">
      <header className="flex flex-col gap-1">
        <h1 className="text-3xl tracking-tight">AI-модели</h1>
        <p className="text-muted-foreground text-sm">Модели и расходы (OpenRouter)</p>
      </header>
      <AiModelsView />
    </div>
  );
}
