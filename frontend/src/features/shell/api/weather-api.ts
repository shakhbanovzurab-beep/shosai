import type { ForecastResponse, TemperatureUnit, WeatherLocation } from "../domain/today-weather";

/** Today's forecast for a location from Open-Meteo, in the given temperature unit. */
export async function fetchForecast(where: WeatherLocation, unit: TemperatureUnit): Promise<ForecastResponse> {
  const params = new URLSearchParams({
    latitude: where.latitude.toFixed(3),
    longitude: where.longitude.toFixed(3),
    current: "temperature_2m,weather_code,is_day",
    daily: "temperature_2m_max,temperature_2m_min",
    temperature_unit: unit,
    timezone: "auto",
    forecast_days: "1",
  });
  const res = await fetch(`https://api.open-meteo.com/v1/forecast?${params}`);
  if (!res.ok) throw new Error(`Weather request failed: ${res.status}`);
  return (await res.json()) as ForecastResponse;
}
