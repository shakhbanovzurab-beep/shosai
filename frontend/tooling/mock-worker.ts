import type { Plugin } from "vite";

import { readFileSync } from "node:fs";
import { createRequire } from "node:module";

/**
 * Отдаёт сервис-воркер MSW с корня (`/mockServiceWorker.js`, область — весь сайт, и /app, и /admin) только
 * в режиме разработки. В сборку он не попадает: production-сборка моков не содержит (F2-D1).
 */
export function mockWorker(): Plugin {
  const require = createRequire(import.meta.url);
  return {
    name: "whisperer:mock-worker",
    apply: "serve",
    configureServer(server) {
      server.middlewares.use("/mockServiceWorker.js", (_request, response) => {
        response.setHeader("content-type", "text/javascript; charset=utf-8");
        response.setHeader("service-worker-allowed", "/");
        response.end(readFileSync(require.resolve("msw/mockServiceWorker.js"), "utf8"));
      });
    },
  };
}
