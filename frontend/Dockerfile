# syntax=docker/dockerfile:1
# Образ edge Shosai: NGINX со статикой кабинета и конфигурацией edge (target architecture §4.2,
# F4 шаг 2). Контекст сборки — корень репозитория: нужны frontend/ и deploy/staging/nginx/.
#
#   docker buildx build -f frontend/Dockerfile --secret id=cabinet_env,src=cabinet.env -t shosai-edge .
#
# cabinet.env — переменные сборки кабинета (VITE_*, frontend/.env.example). Сами значения публичны:
# сборка кладёт их в JS. Файл приходит секретом сборки, а не ARG: так значения не остаются в истории
# и метаданных образа, а Vite читает их как .env.production.local. Без файла кабинет собирается без
# Turnstile, GTM и входа в админку.

ARG NODE_IMAGE=node:26.10.0-trixie-slim
# Вариант -otel несёт модуль ngx_otel_module: корневой span каждого запроса к API (F5).
ARG NGINX_IMAGE=nginxinc/nginx-unprivileged:1.30.6-alpine-otel

FROM ${NODE_IMAGE} AS build
WORKDIR /src/frontend
# Зависимости отдельным слоем: package.json и lock-файл только монтируются, в слой не попадают.
RUN --mount=type=cache,target=/root/.npm \
    --mount=type=bind,source=frontend/package.json,target=package.json \
    --mount=type=bind,source=frontend/package-lock.json,target=package-lock.json \
    npm ci --no-audit --no-fund
COPY --link frontend/ ./
# Сборка сама проверяет dist (tooling/check-dist.ts): без моков, без исходных карт.
RUN --mount=type=secret,id=cabinet_env,target=/src/frontend/.env.production.local,required=false \
    npm run build
COPY --link deploy/staging/nginx/render-csp-hashes.mjs /src/render-csp-hashes.mjs
RUN mkdir /out \
    && node /src/render-csp-hashes.mjs dist/csp-hashes.json /out/csp-hashes.conf \
    && rm dist/csp-hashes.json

FROM ${NGINX_IMAGE} AS edge
LABEL org.opencontainers.image.source="https://github.com/shakhbanovzurab-beep/shosai" \
      org.opencontainers.image.title="shosai-edge" \
      org.opencontainers.image.description="Shosai edge: NGINX with the cabinet's static files" \
      org.opencontainers.image.licenses="LicenseRef-Shosai-Commercial"
# Свой nginx.conf и шаблоны вместо примера образа; подстановка — в tmpfs /tmp при старте.
RUN rm -f /etc/nginx/conf.d/default.conf
COPY --link deploy/staging/nginx/nginx.conf /etc/nginx/nginx.conf
COPY --link deploy/staging/nginx/templates/ /etc/nginx/templates/
COPY --link deploy/staging/nginx/shosai/ /etc/nginx/shosai/
COPY --link --chmod=755 deploy/staging/nginx/entrypoint/05-shosai-rendered-dir.sh /docker-entrypoint.d/
COPY --link --chmod=755 deploy/staging/nginx/entrypoint/25-shosai-optional-servers.sh /docker-entrypoint.d/
COPY --link --from=build /out/csp-hashes.conf /etc/nginx/shosai/csp-hashes.conf
COPY --link --from=build /src/frontend/dist/ /usr/share/nginx/html/app/
ENV NGINX_ENVSUBST_OUTPUT_DIR=/tmp/nginx \
    NGINX_ENVSUBST_FILTER=^SHOSAI_ \
    SHOSAI_API_UPSTREAM=api:8000 \
    SHOSAI_WS_UPSTREAM=ws:8000 \
    SHOSAI_RESOLVER=127.0.0.11 \
    SHOSAI_OTEL_ENDPOINT=collector:4317 \
    SHOSAI_OTEL_TRACE=off \
    SHOSAI_GRAFANA_SERVER_NAME="" \
    SHOSAI_GRAFANA_UPSTREAM=grafana:3000 \
    SHOSAI_CSP_STORAGE_ORIGINS="" \
    SHOSAI_CSP_RTC_ORIGINS="" \
    SHOSAI_TURN_SERVER_NAME="" \
    SHOSAI_TURN_UPSTREAM=livekit:5349 \
    SHOSAI_RTC_SERVER_NAME="" \
    SHOSAI_RTC_UPSTREAM=livekit:7880 \
    SHOSAI_ROBOTS_TAG="noindex, nofollow"
# Пользователь nginx базового образа, без root: порты выше 1024, запись только в /tmp.
USER 101:101
# 8080 — HTTP (ACME и переход на HTTPS), 8443 — HTTPS; 8081 на 127.0.0.1 — проверка здоровья;
# 8082 — stub_status для nginx-экспортёра, только изнутри плоскости.
EXPOSE 8080 8443
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD ["wget", "-q", "-O", "/dev/null", "http://127.0.0.1:8081/health"]
