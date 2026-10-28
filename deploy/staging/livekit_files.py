"""LiveKit on the staging host (meetings A15, ADR 0072 MR-D14): its files and settings.

`render-env.py` writes them with the plane's other files. LiveKit is part of the staging
plane, so the owner's `.env` must hold `LIVEKIT_API_KEY` and `LIVEKIT_API_SECRET`; the
password of LiveKit's Redis is generated once with the plane's other secrets and kept.

- `secrets/livekit.yaml` — the SFU's configuration (uid 65534): its keys, Redis, the media
  ports, TURN behind the edge's TLS on 443 (`external_tls`), the webhook to `api`;
- `secrets/egress.yaml` — egress's configuration (uid 1001): the same keys and Redis;
- `secrets/livekit-redis.acl` — the Redis ACL: one user with a hashed password;
- `telemetry/probe-targets/{livekit,egress}/*.yml` — LiveKit's and egress's metrics targets
  for Prometheus; egress lives in LiveKit's network namespace, so both are `livekit` hosts.

The configuration files are JSON, which LiveKit and egress read as YAML.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

# Единственный публичный IPv4 этой машины (MR-D14): его LiveKit объявляет клиентам в ICE и TURN/UDP.
NODE_IP = "129.101.125.250"
# IPv4 сети плоскости (compose.yaml, networks.plane): только с её адреса LiveKit собирает кандидаты ICE,
# и тот заменяется на NODE_IP. Без фильтра он объявлял бы и свой адрес IPv6 из fd42::/64 — внутреннюю
# адресацию, до которой клиенты снаружи не дойдут.
PLANE_IPV4 = "172.30.42.0/24"
# Предел памяти контейнера livekit в compose.yaml: от него экран администратора считает долю памяти.
LIVEKIT_MEMORY_LIMIT_MB = 512
# Потолки staging (MR-D14): 4 участника звонка, одна видеозапись за раз, не длиннее 30 минут.
STAGING_CEILINGS = {
    "MEETINGS_ROOM_PARTICIPANTS_CEILING": "4",
    "MEETINGS_RECORDINGS_CONCURRENT": "1",
    "MEETINGS_RECORDING_MAX_MINUTES": "30",
}
# Порты медиа (MR-D14); снаружи они те же, что внутри контейнера.
RTC_TCP_PORT = 7881
RTC_UDP_PORT = 7882
TURN_UDP_PORT = 3478
TURN_RELAY_PORTS = (30000, 30099)
# TURN/TLS завершает edge на 443 (stream/turn.conf) и передаёт LiveKit открытый TCP на этот порт.
TURN_PLAIN_PORT = 5349
REDIS_USER = "livekit"
LIVEKIT_USER = (65534, 65534)
EGRESS_USER = (1001, 0)
REDIS_OWNER = (999, 999)
NOBODY = (65534, 65534)
# Стоимость задач egress в долях ядра под его лимит в 1 CPU (замер A7b): иначе он отказывает композиту.
EGRESS_CPU_COST = {
    "room_composite_cpu_cost": 0.9,
    "audio_room_composite_cpu_cost": 0.5,
    "web_cpu_cost": 0.9,
    "participant_cpu_cost": 0.5,
    "track_composite_cpu_cost": 0.5,
    "track_cpu_cost": 0.1,
}

Writer = Callable[[Path, str, tuple[int, int], int], None]


@dataclass(frozen=True, slots=True)
class CallNames:
    """The call's two names under the staging domain, both on the edge's 443."""

    domain: str

    @property
    def rtc(self) -> str:
        """LiveKit's signalling, proxied by the edge."""
        return f"rtc.{self.domain}"

    @property
    def turn(self) -> str:
        """TURN/TLS, terminated by the edge and passed to LiveKit as plain TCP."""
        return f"turn.{self.domain}"


def keys_of(source: dict[str, str]) -> tuple[str, str]:
    """LiveKit's key and secret from the owner's file; staging does not run without them."""
    key, secret = source.get("LIVEKIT_API_KEY", ""), source.get("LIVEKIT_API_SECRET", "")
    if not key or len(secret) < 32:
        message = "LIVEKIT_API_KEY и LIVEKIT_API_SECRET (не короче 32 символов) нужны в .env"
        raise SystemExit(message)
    return key, secret


def redis_settings(password: str) -> dict[str, str]:
    """How LiveKit and egress reach their Redis on the plane's network."""
    return {"address": "livekit-redis:6379", "username": REDIS_USER, "password": password}


def server_config(
    names: CallNames, keys: tuple[str, str], redis_password: str
) -> dict[str, object]:
    """The SFU: signalling for the edge, media on the host's address, TURN behind the edge."""
    key, secret = keys
    return {
        "port": 7880,
        "logging": {"level": "info", "json": True},
        "keys": {key: secret},
        "redis": redis_settings(redis_password),
        "rtc": {
            "tcp_port": RTC_TCP_PORT,
            "udp_port": RTC_UDP_PORT,
            "node_ip": NODE_IP,
            "use_external_ip": False,
            "ips": {"includes": [PLANE_IPV4]},
        },
        "turn": {
            "enabled": True,
            "domain": names.turn,
            "tls_port": TURN_PLAIN_PORT,
            "udp_port": TURN_UDP_PORT,
            "external_tls": True,
            "relay_range_start": TURN_RELAY_PORTS[0],
            "relay_range_end": TURN_RELAY_PORTS[1],
        },
        "room": {"auto_create": False, "empty_timeout": 300, "departure_timeout": 60},
        "webhook": {"api_key": key, "urls": ["http://api:8000/v1/livekit/webhook"]},
        "prometheus": {"port": 6789},
    }


def egress_config(keys: tuple[str, str], redis_password: str) -> dict[str, object]:
    """Egress in LiveKit's network namespace: the server is localhost, Redis a plane service."""
    key, secret = keys
    return {
        "api_key": key,
        "api_secret": secret,
        "ws_url": "ws://localhost:7880",
        "insecure": True,
        "redis": redis_settings(redis_password),
        "health_port": 8080,
        "prometheus_port": 9090,
        "cpu_cost": EGRESS_CPU_COST,
        "logging": {"level": "info", "json": True},
    }


def backend_settings(names: CallNames, keys: tuple[str, str]) -> dict[str, str]:
    """The backend's call settings on staging: clients over the edge, the API on the plane."""
    key, secret = keys
    return {
        "LIVEKIT_URL": f"wss://{names.rtc}",
        "LIVEKIT_API_URL": "http://livekit:7880",
        "LIVEKIT_API_KEY": key,
        "LIVEKIT_API_SECRET": secret,
        "MEETINGS_PROMETHEUS_URL": "http://prometheus:9090",
        "MEETINGS_LIVEKIT_MEMORY_LIMIT_MB": str(LIVEKIT_MEMORY_LIMIT_MB),
        **STAGING_CEILINGS,
    }


def edge_settings(names: CallNames) -> dict[str, str]:
    """The edge's names for calls: signalling on `rtc`, TURN/TLS on `turn`, both on 443."""
    return {
        "SHOSAI_CSP_RTC_ORIGINS": f"wss://{names.rtc} https://{names.rtc}",
        "SHOSAI_RTC_SERVER_NAME": names.rtc,
        "SHOSAI_TURN_SERVER_NAME": names.turn,
    }


def probe_lines(names: CallNames) -> list[str]:
    """Probes of the call's two names through the edge: LiveKit's answer and TURN's TLS."""
    return [
        f'- targets: ["https://{names.rtc}/"]',
        "  labels: {module: https_health, probe: rtc_signal}",
        f'- targets: ["{names.turn}:443"]',
        "  labels: {module: tls_connect, probe: turn_tls}",
    ]


def write_livekit(names: CallNames, source: dict[str, str], redis_password: str, target: Path,
                  acl: Callable[[str, str, str], str], write: Writer) -> None:  # fmt: skip
    """Every LiveKit file under `target`; secrets are readable only by their process's user."""
    keys = keys_of(source)
    secrets_dir = target / "secrets"
    server = json.dumps(server_config(names, keys, redis_password), indent=2)
    write(secrets_dir / "livekit.yaml", server + "\n", LIVEKIT_USER, 0o600)
    egress = json.dumps(egress_config(keys, redis_password), indent=2)
    write(secrets_dir / "egress.yaml", egress + "\n", EGRESS_USER, 0o600)
    write(secrets_dir / "livekit-redis.acl", acl(REDIS_USER, redis_password, "~* &* +@all"),
          REDIS_OWNER, 0o600)  # fmt: skip
    targets = target / "telemetry" / "probe-targets"
    write(targets / "livekit" / "livekit.yml",
          "# LiveKit staging (meetings A15): порт метрик только в сети плоскости.\n"
          '- targets: ["livekit:6789"]\n', NOBODY, 0o644)  # fmt: skip
    write(targets / "egress" / "egress.yml",
          "# Egress staging (meetings A15): в сетевом пространстве LiveKit, только в сети плоскости.\n"
          '- targets: ["livekit:9090"]\n', NOBODY, 0o644)  # fmt: skip
