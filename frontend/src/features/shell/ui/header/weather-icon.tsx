import {
  Cloud,
  CloudDrizzle,
  CloudFog,
  CloudLightning,
  CloudMoon,
  CloudRain,
  CloudSnow,
  CloudSun,
  type LucideIcon,
  type LucideProps,
  Moon,
  Sun,
} from "lucide-react";

import { type ConditionKey, weatherCondition } from "../../domain/weather-codes";

/** Each condition's icon by day and by night; only clear and partly cloudy skies change at night. */
const WEATHER_ICONS: Record<ConditionKey, { day: LucideIcon; night: LucideIcon }> = {
  clear: { day: Sun, night: Moon },
  partly: { day: CloudSun, night: CloudMoon },
  overcast: { day: Cloud, night: Cloud },
  fog: { day: CloudFog, night: CloudFog },
  drizzle: { day: CloudDrizzle, night: CloudDrizzle },
  rain: { day: CloudRain, night: CloudRain },
  snow: { day: CloudSnow, night: CloudSnow },
  storm: { day: CloudLightning, night: CloudLightning },
  unknown: { day: Cloud, night: Cloud },
};

/** The icon for a WMO weather code, with a moon instead of the sun at night. */
export function WeatherIcon({ code, isDay, ...props }: LucideProps & { code: number; isDay: boolean }) {
  const icons = WEATHER_ICONS[weatherCondition(code)];
  const Icon = isDay ? icons.day : icons.night;
  return <Icon {...props} />;
}
