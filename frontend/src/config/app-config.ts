// Только версия: импорт всего package.json затянул бы список зависимостей во входной чанк.
import { version } from "../../package.json";

const currentYear = new Date().getFullYear();

export const APP_CONFIG = {
  name: "Studio Admin",
  version,
  copyright: `© ${currentYear}, Studio Admin.`,
  meta: {
    /** The default page title: the product name, the same in every language. The description is in the `pages` catalog. */
    title: "Studio Admin: Open Source Admin Dashboard with shadcn/ui",
  },
};
