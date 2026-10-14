// Только версия: импорт всего package.json затянул бы список зависимостей во входной чанк.
import { version } from "../../package.json";

const currentYear = new Date().getFullYear();

export const APP_CONFIG = {
  name: "Shosai",
  /** What Shosai is, said the same way in every language: a product name, not a translated phrase. */
  tagline: "AI Workspace",
  version,
  copyright: `© ${currentYear}, Shosai.`,
  meta: {
    /** The default page title: the product name, the same in every language. The description is in the `pages` catalog. */
    title: "Shosai",
  },
};
