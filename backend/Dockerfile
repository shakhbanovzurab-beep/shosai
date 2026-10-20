# syntax=docker/dockerfile:1
# Образ бэкенда Shosai: одна сборка на все роли (target architecture §5, §17). Роль — подкоманда
# `shosai`: api, ws, workers --queue <очередь>, scheduler, migrate, а также команды оператора.
# Собирается в CI из контекста backend/ и не собирается ни на одном сервере (F4, урок черновика).

ARG PYTHON_IMAGE=python:3.14.7-slim-trixie

FROM ghcr.io/astral-sh/uv:0.12.21 AS uv

# Сборка: окружение проекта без dev-зависимостей и без инструментов сборки в рантайме.
FROM ${PYTHON_IMAGE} AS build
COPY --link --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /app
# Зависимости отдельным слоем: меняются реже кода. --frozen, а не --locked: харнесс контрактов
# (dev-группа) лежит вне контекста сборки, а свежесть uv.lock проверяет CI (`uv sync --locked`).
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-dev --no-install-project
COPY --link pyproject.toml uv.lock README.md LICENSE ./
COPY --link src ./src
# Сам проект — обычной установкой: миграции, шаблоны и картинки писем читаются как ресурсы пакета.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

FROM ${PYTHON_IMAGE} AS runtime
LABEL org.opencontainers.image.source="https://github.com/shakhbanovzurab-beep/shosai" \
      org.opencontainers.image.title="shosai-backend" \
      org.opencontainers.image.description="Shosai backend: api, ws, workers, scheduler and migrate roles" \
      org.opencontainers.image.licenses="LicenseRef-Shosai-Commercial"
# ffmpeg и ffprobe — подпроцессы стадий записей (MT-D10): с пределами времени и памяти через
# prlimit (util-linux образа), без сети. Пакеты Debian, без рекомендованных, списки apt удалены.
RUN apt-get update \
    && apt-get install --yes --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*
RUN groupadd --system --gid 1001 shosai \
    && useradd --system --uid 1001 --gid 1001 --no-create-home --shell /usr/sbin/nologin shosai
COPY --link --from=build --chown=1001:1001 /app/.venv /app/.venv
# В контейнере процесс слушает все интерфейсы своей сети; снаружи его открывает только edge.
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    BIND_HOST=0.0.0.0
WORKDIR /app
USER 1001:1001
# HTTP_PORT: публичный порт api и ws; OPS_PORT: /livez, /readyz, /metrics каждой роли.
EXPOSE 8000 9100
ENTRYPOINT ["shosai"]
CMD ["api"]
