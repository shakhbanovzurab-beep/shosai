import type { LiveKitDevice, LiveKitNode } from "../domain/contract";

/* Static data for the in-memory LiveKit demo in `demo-store.ts`. */

export const MINUTE = 60_000;
export const HOUR = 60 * MINUTE;
/** Average per-participant traffic through the SFU: uplink in, fan-out down. */
export const MBPS_IN_PER_PARTICIPANT = 1.4;
export const MBPS_OUT_PER_PARTICIPANT = 3.1;
/** Roughly what a composite 720p recording writes per minute. */
export const RECORDING_BYTES_PER_MINUTE = 9 * 1024 * 1024;
/** How long the demo server has been up when the process starts. */
export const DEMO_UPTIME_MS = (12 * 24 + 5) * HOUR + 17 * MINUTE;

export const PEOPLE = [
  ["Анна Смирнова", "anna.smirnova"],
  ["Игорь Петров", "igor.petrov"],
  ["Мария Кузнецова", "maria.kuznetsova"],
  ["Дмитрий Волков", "dmitry.volkov"],
  ["Ольга Соколова", "olga.sokolova"],
  ["Алексей Морозов", "alexey.morozov"],
  ["Екатерина Новикова", "ekaterina.novikova"],
  ["Сергей Лебедев", "sergey.lebedev"],
  ["Наталья Козлова", "natalia.kozlova"],
  ["Павел Орлов", "pavel.orlov"],
  ["Юлия Васильева", "yulia.vasilieva"],
  ["Андрей Фёдоров", "andrey.fedorov"],
  ["Ирина Попова", "irina.popova"],
  ["Михаил Егоров", "mikhail.egorov"],
  ["Татьяна Михайлова", "tatiana.mikhailova"],
  ["Николай Зайцев", "nikolay.zaytsev"],
  ["Светлана Белова", "svetlana.belova"],
  ["Артём Григорьев", "artem.grigoriev"],
] as const;

export const DEVICES: LiveKitDevice[] = [
  { os: "macos", os_version: "macOS 15.1", client: "desktop", client_version: "2.4.1", browser: null },
  { os: "macos", os_version: "macOS 14.6", client: "desktop", client_version: "2.4.0", browser: null },
  { os: "windows", os_version: "Windows 11 23H2", client: "desktop", client_version: "2.4.0", browser: null },
  { os: "windows", os_version: "Windows 10 22H2", client: "desktop", client_version: "2.3.7", browser: null },
  { os: "macos", os_version: "macOS 15.0", client: "web", client_version: null, browser: "Chrome 141" },
  { os: "linux", os_version: "Ubuntu 24.04", client: "web", client_version: null, browser: "Firefox 143" },
  { os: "windows", os_version: "Windows 11 24H2", client: "web", client_version: null, browser: "Edge 141" },
  { os: "ios", os_version: "iOS 18.1", client: "mobile", client_version: "2.4.1", browser: null },
  { os: "android", os_version: "Android 15", client: "mobile", client_version: "2.4.0", browser: null },
];

export const VIDEO_CODECS = ["VP8", "VP8", "H264", "VP9", "AV1"] as const;

/** Nodes with the idle load they start from; participants add to it. */
export const DEMO_NODES: (Omit<LiveKitNode, "rooms" | "participants" | "cpu_percent" | "memory_percent"> & {
  cpu_base: number;
  memory_base: number;
})[] = [
  { id: "ND_nx5AiRuYWtxy", state: "serving", cpu_base: 14, memory_base: 38 },
  { id: "ND_q81LmVf2DcKe", state: "serving", cpu_base: 22, memory_base: 51 },
  { id: "livekit-3:6789", state: "down", cpu_base: 0, memory_base: 0 },
];

/** Finished recordings: how long ago they started, minutes recorded, outcome. */
export const FINISHED_EGRESS = [
  [26 * HOUR, 52, "complete"],
  [20 * HOUR, 38, "complete"],
  [6 * HOUR, 64, "complete"],
  [3 * HOUR, 0, "failed"],
] as const;

/** Rooms open at start: minutes since they began, participants, recording. */
export const OPEN_ROOMS = [
  [48, 7, true],
  [31, 4, false],
  [12, 2, false],
  [6, 5, true],
  [3, 3, false],
] as const;
