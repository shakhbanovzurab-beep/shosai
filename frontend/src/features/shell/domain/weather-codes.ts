export type ConditionKey = "clear" | "partly" | "overcast" | "fog" | "drizzle" | "rain" | "snow" | "storm" | "unknown";

/** WMO weather interpretation codes, as returned by Open-Meteo, grouped into what the header shows. */
const CONDITIONS: { codes: number[]; key: ConditionKey }[] = [
  { codes: [0], key: "clear" },
  { codes: [1, 2], key: "partly" },
  { codes: [3], key: "overcast" },
  { codes: [45, 48], key: "fog" },
  { codes: [51, 53, 55, 56, 57], key: "drizzle" },
  { codes: [61, 63, 65, 66, 67, 80, 81, 82], key: "rain" },
  { codes: [71, 73, 75, 77, 85, 86], key: "snow" },
  { codes: [95, 96, 99], key: "storm" },
];

export function weatherCondition(code: number): ConditionKey {
  return CONDITIONS.find((c) => c.codes.includes(code))?.key ?? "unknown";
}
