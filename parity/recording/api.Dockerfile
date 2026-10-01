# syntax=docker/dockerfile:1
#
# API черновика для записи фикстур стенда сравнения.
#
# Это эталон, а не код v2: Python, зависимости и исходники — те, что у черновика
# на закреплённом коммите (именованный контекст `draft` — каталог backend его
# экспорта, см. scripts/export-draft.sh). Отличия от образа черновика только
# такие, без которых запись невоспроизводима:
#   * libfaketime — процесс видит фиксированный момент стенда сравнения, поэтому «дней
#     осталось», «сегодня» и метки создания не зависят от дня записи;
#   * нет ffmpeg и статики лендинга — записываемым экранам они не нужны.

ARG PYTHON_IMAGE=python:3.12-slim@sha256:f77ac9e44ae96ef2c90b8053ea08c31f8be030f824196b0ae4db6d462c84e51f

FROM ${PYTHON_IMAGE} AS dependencies
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install uv==0.12.21
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,from=draft,source=requirements.txt,target=/tmp/draft/requirements.txt \
    uv pip install --system -r /tmp/draft/requirements.txt

FROM ${PYTHON_IMAGE} AS runtime
# Кэш apt живёт в cache-mount, поэтому штатная очистка образа отключена.
RUN rm -f /etc/apt/apt.conf.d/docker-clean
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends libfaketime

RUN groupadd --system --gid 1001 draft \
    && useradd --system --uid 1001 --gid draft --home-dir /app draft

COPY --from=dependencies /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=dependencies /usr/local/bin /usr/local/bin

WORKDIR /app
COPY --link --chown=1001:1001 --from=draft src/ ./src/
COPY --link --chown=1001:1001 --from=draft alembic/ ./alembic/
COPY --link --chown=1001:1001 --from=draft alembic.ini ./alembic.ini
COPY --link --chown=1001:1001 --from=draft assets/ ./assets/
COPY --link --chown=1001:1001 --from=draft data/ ./data/
COPY --link --chown=1001:1001 --from=draft trust/ ./trust/
COPY --link --chown=1001:1001 --from=draft static/email/ ./static/email/

# Каталоги, которые настройки черновика создают на старте, — сразу с владельцем.
RUN install -d -o 1001 -g 1001 /app/knowledge_base /app/data/user_context /app/data/builds

# FAKETIME задаёт compose: без него библиотека подгружена, но время настоящее.
# Монотонные часы не подменяются: иначе встанут таймеры asyncio.
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    LD_PRELOAD=/usr/lib/x86_64-linux-gnu/faketime/libfaketime.so.1 \
    FAKETIME_DONT_FAKE_MONOTONIC=1

USER 1001
EXPOSE 8000
HEALTHCHECK --interval=5s --timeout=3s --retries=30 --start-period=10s \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"]
CMD ["uvicorn", "meetassist.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
