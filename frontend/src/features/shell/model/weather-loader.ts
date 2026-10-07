import { fetchForecast } from "../api/weather-api";
import {
  FALLBACK_COORDS,
  temperatureUnit,
  toTodayWeather,
  type WeatherLocation,
  type WeatherResult,
} from "../domain/today-weather";

const GEOLOCATION_TIMEOUT_MS = 8000;

const locate = () =>
  new Promise<WeatherLocation>((resolve) => {
    const fallback = { ...FALLBACK_COORDS, fallback: true };
    if (!("geolocation" in navigator)) return resolve(fallback);
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => resolve({ latitude: coords.latitude, longitude: coords.longitude, fallback: false }),
      () => resolve(fallback),
      { timeout: GEOLOCATION_TIMEOUT_MS },
    );
  });

const fetchWeather = async (where: WeatherLocation, language: string) => {
  const unit = temperatureUnit(language);
  return toTodayWeather(await fetchForecast(where, unit), where, unit);
};

// The location is asked for once per page load; each key gets one request, shared by every reader.
let location: Promise<WeatherLocation> | null = null;
let cached: { key: string; promise: Promise<WeatherResult> } | null = null;

/** Today's weather for a key from useWeatherKey ("bucket|language"), for React's `use()`. Never rejects. */
export function loadTodayWeather(key: string): Promise<WeatherResult> {
  if (cached?.key === key) return cached.promise;
  location ??= locate();
  const language = key.slice(key.indexOf("|") + 1);
  const promise = location
    .then((where) => fetchWeather(where, language))
    .then(
      (weather): WeatherResult => ({ status: "ready", weather }),
      (): WeatherResult => ({ status: "error" }),
    );
  cached = { key, promise };
  return promise;
}
