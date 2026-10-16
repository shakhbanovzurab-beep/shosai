#!/bin/sh
# Сквозная проверка §16.8 (план F5, шаг 4): запросы с канареечными значениями идут через edge, потом
# канарейки ищутся во всём, что за это время легло в Loki, Tempo и Prometheus. Найдено — код 1.
#
# Запросы ничего не сохраняют (проверка идёт и на staging): неверный вход, сброс пароля по адресу,
# чужие bearer-токен и cookie, адрес почты в пути, токен в строке запроса, свой user agent и подложный
# X-Forwarded-For. Полный путь регистрации с кодом и токенами проверяет тест бэкенда
# tests/features/identity/test_telemetry_privacy.py.
#
# Проверка не пустая: строки этих запросов должны найтись в Loki, а трейс входа — в Tempo, если вход
# был медленнее порога выборки (после нескольких неудачных входов с одного адреса identity просит
# капчу и отвечает быстро — тогда трейс не хранится, и Tempo проверен по остальным трейсам окна). Канарейка
# не пишется в запрос к Loki буквально (Loki пишет тексты запросов в свой журнал): cnry(?:)…
#
#   deploy/observability/checks/privacy-canary.sh                        # локальный стек
#   EDGE_URL=https://shosai.tech LOKI_URL=… TEMPO_URL=… PROMETHEUS_URL=… STORE_AUTH=user:pass …
#
# Переменные: EDGE_URL, LOKI_URL, TEMPO_URL, PROMETHEUS_URL — адреса; STORE_AUTH — user:pass для трёх
# хранилищ (через прокси источников Grafana); WAIT_SECONDS — ожидание конвейера (по умолчанию 75: Tempo
# ищет по свежим трейсам с задержкой до ~30 с после хвостовой выборки);
# CANARY_MARK — метка вместо случайной, для проверки самой проверки.
set -eu

EDGE_URL=${EDGE_URL:-https://127.0.0.1:18443}
LOKI_URL=${LOKI_URL:-http://127.0.0.1:3100}
TEMPO_URL=${TEMPO_URL:-http://127.0.0.1:3200}
PROMETHEUS_URL=${PROMETHEUS_URL:-http://127.0.0.1:9090}
STORE_AUTH=${STORE_AUTH:-}
WAIT_SECONDS=${WAIT_SECONDS:-75}

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

# Самоподписанный сертификат бывает только у локального edge.
edge_tls=""
case "$EDGE_URL" in
  https://127.0.0.1*|https://localhost*) edge_tls="--insecure" ;;
esac

# CANARY_MARK задаёт метку заранее — только чтобы проверить саму проверку подложенной утечкой.
mark=${CANARY_MARK:-cnry$(od -An -N6 -tx1 /dev/urandom | tr -d ' \n')}
client_ip="203.0.113.77"
email="$mark.person@example.test"
token_like="eyJ${mark}aaaaaaaa.eyJ${mark}bbbbbbbb.${mark}cccccccc"
started=$(date +%s)

edge() {
  # $1 — метод, $2 — путь, $3 — тело JSON или пусто; остальное — заголовки curl.
  method=$1 path=$2 body=$3
  shift 3
  curl -sS -m 15 $edge_tls -o /dev/null -D - -w 'x-time-total: %{time_total}\n' -X "$method" "$EDGE_URL$path" \
    -H "User-Agent: CanaryAgent/$mark" -H "X-Forwarded-For: $client_ip" \
    -H 'Content-Type: application/json' ${body:+--data "$body"} "$@" \
    | tr -d '\r' > "$work/last-response"
  awk 'tolower($1) == "x-request-id:" { print $2 }' "$work/last-response" >> "$work/request-ids"
}

edge POST /v1/auth/login "{\"email\":\"$email\",\"password\":\"$mark-password\"}"
login_seconds=$(awk '$1 == "x-time-total:" { print $2 }' "$work/last-response")
edge POST /v1/auth/password/forgot "{\"email\":\"$email\"}"
edge GET /v1/auth/me "" -H "Authorization: Bearer $token_like"
edge POST /v1/auth/refresh "" -H "Cookie: refresh_token=$token_like; session=$mark-session"
edge GET "/v1/people/$email?token=$mark-query" ""
echo "запросы с канарейкой $mark отправлены: $(wc -l < "$work/request-ids") ответов с X-Request-ID"

sleep "$WAIT_SECONDS"
ended=$(( $(date +%s) + 5 ))

store() {
  # $1 — файл ответа, $2 — URL; остальное — параметры curl.
  out=$1 url=$2
  shift 2
  curl -sS -m 60 -G ${STORE_AUTH:+-u "$STORE_AUTH"} -o "$out" "$url" "$@"
}

# Loki: все строки окна с канарейкой или адресом клиента и все строки наших запросов.
needle="${mark%"${mark#????}"}(?:)${mark#????}|203\.0\.113\.77"
store "$work/loki-leaks.json" "$LOKI_URL/loki/api/v1/query_range" \
  --data-urlencode "query={service=~\".+\"} |~ \`(?i)($needle)\`" \
  --data-urlencode "start=$(( started - 5 ))000000000" --data-urlencode "end=${ended}000000000" \
  --data-urlencode limit=100
ids=$(paste -sd '|' "$work/request-ids")
store "$work/loki-requests.json" "$LOKI_URL/loki/api/v1/query_range" \
  -H 'X-Loki-Response-Encoding-Flags: categorize-labels' \
  --data-urlencode "query={service=~\".+\"} | request_id=~\"$ids\"" \
  --data-urlencode "start=$(( started - 5 ))000000000" --data-urlencode "end=${ended}000000000" \
  --data-urlencode limit=1000

# Tempo: все трейсы окна; Prometheus: все ряды окна и exemplars HTTP-метрики.
store "$work/tempo-search.json" "$TEMPO_URL/api/search" --data-urlencode 'q={}' \
  --data-urlencode "start=$(( started - 5 ))" --data-urlencode "end=$ended" --data-urlencode limit=2000
store "$work/prometheus-series.json" "$PROMETHEUS_URL/api/v1/series" \
  --data-urlencode 'match[]={__name__=~".+"}' --data-urlencode "start=$(( started - 5 ))" \
  --data-urlencode "end=$ended"
store "$work/prometheus-exemplars.json" "$PROMETHEUS_URL/api/v1/query_exemplars" \
  --data-urlencode 'query=http_server_request_duration_seconds_bucket' \
  --data-urlencode "start=$(( started - 5 ))" --data-urlencode "end=$ended"

python3 -I - "$work" "$mark" "$client_ip" "$TEMPO_URL" "$STORE_AUTH" "$login_seconds" <<'PY'
import base64, json, pathlib, sys, urllib.request

work, mark, client_ip, tempo, auth, login_seconds = sys.argv[1:7]
# Порог хвостовой выборки коллектора (300 мс) с запасом на путь до edge.
SLOW_LOGIN_SECONDS = 0.35
needles = (mark.lower(), client_ip)
folder = pathlib.Path(work)


def load(name):
    text = (folder / name).read_text()
    try:
        return json.loads(text)
    except ValueError:
        sys.exit(f"{name}: хранилище ответило не JSON: {text[:300]}")


def leaked(text):
    lowered = text.lower()
    return [needle for needle in needles if needle in lowered]


def fetch(url):
    request = urllib.request.Request(url)
    if auth:
        request.add_header("Authorization", "Basic " + base64.b64encode(auth.encode()).decode())
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode()


problems = []
loki_hits = [v[1] for r in load("loki-leaks.json")["data"]["result"] for v in r["values"]]
problems += [f"Loki: {line[:300]}" for line in loki_hits]

ours = load("loki-requests.json")["data"]["result"]
services = {r["stream"].get("service") for r in ours}
traces = {v[2]["structuredMetadata"].get("trace_id") for r in ours for v in r["values"]
          if len(v) > 2 and "structuredMetadata" in v[2]}
traces.discard(None)
traces.discard("")
if not {"edge", "api"} <= services:
    problems.append(f"Loki: нет строк наших запросов от edge и api (нашлись: {sorted(services)})")

found_ours = 0
search = load("tempo-search.json").get("traces", [])
for item in search:
    body = fetch(f"{tempo}/api/v2/traces/{item['traceID']}")
    if item["traceID"] in traces and '"spans"' in body:
        found_ours += 1
    problems += [f"Tempo, трейс {item['traceID']}: {n}" for n in leaked(body)]
if float(login_seconds) > SLOW_LOGIN_SECONDS and not found_ours:
    problems.append(f"Tempo: нет трейса входа за {login_seconds} с (проверка была бы пустой)")
elif not found_ours:
    print(f"внимание: вход ответил за {login_seconds} с (капча после неудач?), его трейс не хранится;"
          f" Tempo проверен по {len(search)} трейсам окна")

for name in ("prometheus-series.json", "prometheus-exemplars.json"):
    problems += [f"Prometheus ({name}): {n}" for n in leaked((folder / name).read_text())]

print(f"Loki: строк наших запросов {sum(len(r['values']) for r in ours)} от {sorted(services)}; "
      f"Tempo: трейсов в окне {len(search)}, наших {found_ours}; "
      f"Prometheus: рядов {len(load('prometheus-series.json')['data'])}")
if problems:
    print("канарейки найдены:", *problems, sep="\n  ")
    sys.exit(1)
print("канареек нет ни в логах, ни в трейсах, ни в метриках")
PY
