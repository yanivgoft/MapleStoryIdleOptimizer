"""Runtime configuration, all from environment variables (read once per ``Settings.from_env()`` call, so tests can build their own)."""
import os
from dataclasses import dataclass

DEFAULT_CORS = "http://localhost:5173,http://127.0.0.1:5173"


def _int(name, default):
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        raise SystemExit(f"environment variable {name} must be an integer (got {raw!r})")


@dataclass(frozen=True)
class Settings:
    cors_origins: tuple = tuple(DEFAULT_CORS.split(","))   # MSI_CORS_ORIGINS="https://a.example,https://b.example" ("*" allows any)
    rate_limit_per_minute: int = 120                        # MSI_RATE_LIMIT_PER_MINUTE, per client IP on /api/*; 0 disables
    rate_limit_burst_window_s: int = 60                     # MSI_RATE_LIMIT_WINDOW_S: sliding window length
    max_body_bytes: int = 65536                             # MSI_MAX_BODY_BYTES: request body cap (an inputs dict is ~2 KB)
    proxy_hops: int = 0                                     # MSI_PROXY_HOPS: trusted reverse proxies in front (0 = use the socket peer)
    log_level: str = "INFO"                                 # MSI_LOG_LEVEL
    rate_limit_sens_per_minute: int = 20                    # MSI_RATE_LIMIT_SENS_PER_MIN: per client IP on POST .../sensitivity (one call ~0.5 s); 0 disables
    sens_cache_entries: int = 128                           # MSI_SENS_CACHE_ENTRIES: LRU size of the sensitivity result cache; 0 disables
    sens_cache_ttl_s: int = 600                             # MSI_SENS_CACHE_TTL_S: lifetime of a cached sensitivity result
    sens_timeout_s: int = 30                                # MSI_SENS_TIMEOUT_S: request guard; a slower call answers 504 (the worker thread finishes in the background)
    sens_workers: int = 2                                   # MSI_SENS_WORKERS: sensitivity calls evaluated at the same time (the rest wait for a worker)
    rate_limit_cubes_per_minute: int = 20                   # MSI_RATE_LIMIT_CUBES_PER_MIN: per client IP on POST .../cubes (the UI sends ~5 requests per Calculate); 0 disables
    rate_limit_compare_per_minute: int = 60                 # MSI_RATE_LIMIT_COMPARE_PER_MIN: per client IP on POST .../equipment-compare and .../artifact-potentials; 0 disables
    cubes_cache_entries: int = 256                          # MSI_CUBES_CACHE_ENTRIES: LRU size of the per-ROW cube result cache (a full call = 30 rows) and switch of the pricing caches; 0 disables
    cubes_cache_ttl_s: int = 600                            # MSI_CUBES_CACHE_TTL_S: lifetime of a cached cube result / pricing
    cubes_timeout_s: int = 45                               # MSI_CUBES_TIMEOUT_S: request guard of /cubes (504 after this; a full 30-row call is ~3-6 s)
    cubes_workers: int = 2                                  # MSI_CUBES_WORKERS: cube evaluations running at the same time

    @classmethod
    def from_env(cls):
        origins = tuple(o.strip() for o in os.environ.get("MSI_CORS_ORIGINS", DEFAULT_CORS).split(",") if o.strip())
        return cls(
            cors_origins=origins,
            rate_limit_per_minute=_int("MSI_RATE_LIMIT_PER_MINUTE", 120),
            rate_limit_burst_window_s=max(1, _int("MSI_RATE_LIMIT_WINDOW_S", 60)),
            max_body_bytes=_int("MSI_MAX_BODY_BYTES", 65536),
            proxy_hops=_int("MSI_PROXY_HOPS", 0),
            log_level=os.environ.get("MSI_LOG_LEVEL", "INFO").upper(),
            rate_limit_sens_per_minute=_int("MSI_RATE_LIMIT_SENS_PER_MIN", 20),
            sens_cache_entries=max(0, _int("MSI_SENS_CACHE_ENTRIES", 128)),
            sens_cache_ttl_s=max(1, _int("MSI_SENS_CACHE_TTL_S", 600)),
            sens_timeout_s=max(1, _int("MSI_SENS_TIMEOUT_S", 30)),
            sens_workers=max(1, _int("MSI_SENS_WORKERS", 2)),
            rate_limit_cubes_per_minute=_int("MSI_RATE_LIMIT_CUBES_PER_MIN", 20),
            rate_limit_compare_per_minute=_int("MSI_RATE_LIMIT_COMPARE_PER_MIN", 60),
            cubes_cache_entries=max(0, _int("MSI_CUBES_CACHE_ENTRIES", 256)),
            cubes_cache_ttl_s=max(1, _int("MSI_CUBES_CACHE_TTL_S", 600)),
            cubes_timeout_s=max(1, _int("MSI_CUBES_TIMEOUT_S", 45)),
            cubes_workers=max(1, _int("MSI_CUBES_WORKERS", 2)),
        )
