/** Переменные сборки кабинета; описаны в frontend/.env.example. */
interface ImportMetaEnv {
  readonly VITE_GTM_CONTAINER_ID?: string;
  readonly VITE_TURNSTILE_SITE_KEY?: string;
  readonly VITE_ADMIN_LOGIN_PATH?: string;
}
