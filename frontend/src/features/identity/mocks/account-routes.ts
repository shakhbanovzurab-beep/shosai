// Аватар, устройства, выгрузка и удаление аккаунта в `npm run dev` без бэкенда. Удаление требует свежего входа,
// если адрес начинается с «stale»; выгрузка «собирается» несколько секунд.
import { demoMe, setAvatarUrl } from "./demo-person";

const EXPORT_SECONDS = 4;

let devices = [
  { id: "d-this", client_kind: "web", device_label: "Chrome · macOS", ip: "10.0.0.2", current: true },
  { id: "d-mac", client_kind: "desktop", device_label: "Shosai · MacBook Pro", ip: "10.0.0.3", current: false },
  { id: "d-phone", client_kind: "web", device_label: "Safari · iPhone", ip: "10.0.0.4", current: false },
].map((device, index) => ({
  ...device,
  created_at: `2026-10-0${index + 1}T09:00:00Z`,
  last_used_at: `2026-10-1${index + 1}T09:00:00Z`,
}));

let exportRequestedAt: number | null = null;

const refused = (code: string, status: number) =>
  Response.json({ error: { code, request_id: "mock-request" }, detail: code }, { status });

export const avatarRoute = {
  async PUT(request: Request) {
    const image = await request.blob();
    return Response.json(setAvatarUrl(URL.createObjectURL(image)));
  },
  DELETE() {
    return Response.json(setAvatarUrl(null));
  },
};

export const devicesRoute = {
  GET() {
    return Response.json({ items: devices, next_cursor: null });
  },
};

export const deviceRoute = {
  async DELETE(_request: Request, { params }: { params: Promise<{ device_id: string }> }) {
    const { device_id: deviceId } = await params;
    devices = devices.filter((device) => device.id !== deviceId);
    return new Response(null, { status: 204 });
  },
};

export const otherDevicesRoute = {
  POST() {
    const ended = devices.filter((device) => !device.current).length;
    devices = devices.filter((device) => device.current);
    return Response.json({ ended });
  },
};

function exportJob() {
  if (exportRequestedAt === null) return null;
  const ready = Date.now() - exportRequestedAt > EXPORT_SECONDS * 1000;
  const requested = new Date(exportRequestedAt).toISOString();
  const expires = new Date(exportRequestedAt + 7 * 86_400_000).toISOString();
  return {
    id: "export-1",
    state: ready ? "ready" : "running",
    requested_at: requested,
    ready_at: ready ? requested : null,
    expires_at: ready ? expires : null,
    size_bytes: ready ? 4_812_377 : null,
    download_url: ready ? "/app/mock-export.zip" : null,
    download_expires_at: ready ? expires : null,
  };
}

export const exportsRoute = {
  POST() {
    exportRequestedAt = Date.now();
    return Response.json(exportJob(), { status: 202 });
  },
};

export const latestExportRoute = {
  GET() {
    const job = exportJob();
    return job === null ? refused("export_not_found", 404) : Response.json(job);
  },
};

export const deletionRoute = {
  async POST(request: Request) {
    const body = (await request.json()) as { confirm_email?: string };
    const email = demoMe().email;
    if ((body.confirm_email ?? "").trim().toLowerCase() !== email) return refused("confirmation_mismatch", 400);
    if (email.startsWith("stale")) return refused("reauthentication_required", 403);
    return Response.json({ erase_at: new Date(Date.now() + 7 * 86_400_000).toISOString() }, { status: 202 });
  },
};
