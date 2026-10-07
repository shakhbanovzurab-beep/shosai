import { type ConditionKey, weatherCondition } from "./weather-codes";

/** Used when the browser can't or won't share its location; its name comes from the `weather` messages. */
export const FALLBACK_COORDS = { latitude: 55.7558, longitude: 37.6173 };

export type WeatherLocation = { latitude: number; longitude: number; fallback: boolean };

export type TemperatureUnit = "celsius" | "fahrenheit";

/** Everything the header shows, as data: the header words and formats it in the interface language. */
export type TodayWeather = {
  code: number;
  isDay: boolean;
  condition: ConditionKey;
  unit: TemperatureUnit;
  now: number;
  high: number;
  low: number;
  /** The reading is for FALLBACK_COORDS, so the header names the place. */
  fallback: boolean;
};

export type WeatherResult = { status: "error" } | { status: "ready"; weather: TodayWeather };

/** The part of Open-Meteo's forecast response the header reads. */
export type ForecastResponse = {
  current: { temperature_2m: number; weather_code: number; is_day: number };
  daily: { temperature_2m_max: number[]; temperature_2m_min: number[] };
};

/** Regions that report temperature in Fahrenheit. */
const FAHRENHEIT_REGIONS = new Set(["US", "LR", "MM", "BS", "BZ", "KY", "PW", "FM", "MH"]);

/** Fahrenheit only when the language names such a region explicitly (`en-US`); a bare `en` stays in Celsius. */
export const temperatureUnit = (language: string): TemperatureUnit =>
  FAHRENHEIT_REGIONS.has(new Intl.Locale(language).region ?? "") ? "fahrenheit" : "celsius";

export function toTodayWeather(data: ForecastResponse, where: WeatherLocation, unit: TemperatureUnit): TodayWeather {
  return {
    code: data.current.weather_code,
    isDay: data.current.is_day === 1,
    condition: weatherCondition(data.current.weather_code),
    unit,
    now: data.current.temperature_2m,
    high: data.daily.temperature_2m_max[0],
    low: data.daily.temperature_2m_min[0],
    fallback: where.fallback,
  };
}
