import { Suspense } from "react";

import { ErrorsOverview, ErrorsOverviewSkeleton } from "./errors-overview";

/** Admin › Errors: the page heading over the KPIs, timeline and issue list. */
export function ErrorsScreen() {
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        <h1 className="font-semibold text-2xl tracking-tight">Ошибки</h1>
        <p className="text-muted-foreground text-sm">
          Сбои и исключения платформы (веб, API, агент) и клиентов для macOS и Windows.
        </p>
      </div>
      {/* Filters live in the URL, which is only known in the browser. */}
      <Suspense fallback={<ErrorsOverviewSkeleton />}>
        <ErrorsOverview />
      </Suspense>
    </div>
  );
}
