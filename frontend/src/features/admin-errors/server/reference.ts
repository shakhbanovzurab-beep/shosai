import type { Assignee, IssueUser } from "../domain/contract";
import type { ErrorSource } from "../domain/dimensions";

/* Reference data of the errors demo: admins, users, builds and environments. */

export const ASSIGNEES: Assignee[] = [
  { id: "adm_anna", name: "Анна Смирнова", email: "anna.smirnova@leo.app" },
  { id: "adm_dmitry", name: "Дмитрий Орлов", email: "dmitry.orlov@leo.app" },
  { id: "adm_elena", name: "Елена Кузнецова", email: "elena.kuznetsova@leo.app" },
  { id: "adm_maxim", name: "Максим Волков", email: "maxim.volkov@leo.app" },
];

const USER_NAMES = [
  ["Иван Петров", "ivan.petrov"],
  ["Мария Соколова", "maria.sokolova"],
  ["Алексей Морозов", "alexey.morozov"],
  ["Ольга Лебедева", "olga.lebedeva"],
  ["Сергей Козлов", "sergey.kozlov"],
  ["Наталья Новикова", "natalia.novikova"],
  ["Павел Федоров", "pavel.fedorov"],
  ["Татьяна Михайлова", "tatiana.mikhailova"],
  ["Андрей Васильев", "andrey.vasiliev"],
  ["Екатерина Павлова", "ekaterina.pavlova"],
  ["Михаил Семенов", "mikhail.semenov"],
  ["Юлия Голубева", "yulia.golubeva"],
  ["Николай Виноградов", "nikolay.vinogradov"],
  ["Анастасия Богданова", "anastasia.bogdanova"],
  ["Владимир Воробьев", "vladimir.vorobiev"],
  ["Ирина Зайцева", "irina.zaytseva"],
  ["Артем Соловьев", "artem.soloviev"],
  ["Светлана Борисова", "svetlana.borisova"],
  ["Роман Яковлев", "roman.yakovlev"],
  ["Ксения Григорьева", "ksenia.grigorieva"],
  ["Денис Романов", "denis.romanov"],
  ["Полина Степанова", "polina.stepanova"],
  ["Георгий Никитин", "georgy.nikitin"],
  ["Вера Захарова", "vera.zakharova"],
] as const;

export const USERS = new Map<string, IssueUser>(
  USER_NAMES.map(([name, login], index) => {
    const id = `usr_${String(index + 1).padStart(3, "0")}`;
    return [id, { id, name, email: `${login}@example.com` }];
  }),
);
export const USER_IDS = [...USERS.keys()];

/** Oldest first; newer events are more likely to run newer builds. */
export const VERSIONS: Record<ErrorSource, string[]> = {
  platform: ["2026.9.28", "2026.10.1", "2026.10.4"],
  macos: ["2.4.0", "2.4.1", "2.5.0"],
  windows: ["2.4.0", "2.4.1", "2.5.0"],
};

export const ENVIRONMENTS: Record<ErrorSource, { devices: string[]; os: string[] }> = {
  platform: {
    devices: ["Chrome 141 · macOS", "Chrome 141 · Windows", "Safari 26 · macOS", "Firefox 143 · Windows"],
    os: ["macOS 15.5", "Windows 11 24H2", "macOS 26.0", "Windows 10 22H2"],
  },
  macos: {
    devices: ["MacBook Pro (M3, 14″)", "MacBook Air (M2, 13″)", "iMac (M4)", "Mac mini (M2)"],
    os: ["macOS 15.5 (24F74)", "macOS 26.0 (25A354)", "macOS 14.7.6 (23H626)"],
  },
  windows: {
    devices: ["Dell XPS 13 9340", "Lenovo ThinkPad X1 Carbon Gen 12", "HP EliteBook 840 G10", "Surface Laptop 7"],
    os: ["Windows 11 24H2 (26100.4061)", "Windows 11 23H2 (22631.5335)", "Windows 10 22H2 (19045.5854)"],
  },
};

export const SERVER_ENVIRONMENT = {
  devices: ["api-7f9c · eu-central-1", "api-21ab · eu-central-1"],
  os: ["Linux 6.8"],
};

/** Sessions per 24 hours used to turn crash counts into a crash-free rate. */
export const DESKTOP_SESSIONS = { macos: 18_420, windows: 26_815 } as const;
