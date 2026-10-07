import { WorkspacesOverview } from "./workspaces-overview";

/** Admin › Пространства: the page heading over the summary and the list. */
export function WorkspacesScreen() {
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        <h1 className="font-semibold text-2xl tracking-tight">Пространства</h1>
        <p className="text-muted-foreground text-sm">
          Рабочие пространства команд на платформе: места, оплата, активность и доступ.
        </p>
      </div>
      <WorkspacesOverview />
    </div>
  );
}
