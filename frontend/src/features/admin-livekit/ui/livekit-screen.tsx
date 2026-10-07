import { LiveKitDashboard } from "./livekit-dashboard";

/** Admin › LiveKit: the page heading over the live dashboard. */
export function LiveKitScreen() {
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        <h1 className="text-3xl tracking-tight">LiveKit</h1>
        <p className="text-muted-foreground text-sm">
          Сервер видеозвонков: состояние, нагрузка и активные встречи Leo.
        </p>
      </div>
      <LiveKitDashboard />
    </div>
  );
}
