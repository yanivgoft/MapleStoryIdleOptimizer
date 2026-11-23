"""FastAPI application: stateless DPS API.  ``uvicorn api.main:app`` from the repository root.

GET  /api/health
GET  /api/classes
GET  /api/classes/{id}/schema
GET  /api/classes/{id}/defaults?content_type=...
POST /api/classes/{id}/compute          body: inputs dict (missing keys take the content type's defaults)
POST /api/classes/{id}/sensitivity      body: the same inputs + optional ``which`` / ``companion_comparison_level`` / ``artifact_stars`` -> stat values
GET  /api/classes/{id}/sensitivity/meta labels / types / notes of the stats and artifact toggles
GET  /api/classes/{id}/cubes/meta       slots, rarities, stat options, pity caps, milestones (+ equipment-compare / artifact-potential tables)
POST /api/classes/{id}/cubes            inputs + ``gear`` (+ ``only``) -> cube optimizer rows (engine.cubes.recommend)
POST /api/classes/{id}/equipment-compare  inputs + ``current`` / ``new`` equips -> Total DPS gain of each, delta (engine.equipment.compare)
POST /api/classes/{id}/artifact-potentials  inputs + ``potentials`` -> DPS gain per artifact potential line (engine.potentials)
"""
import asyncio
import json
import logging
import math
import sys
from concurrent.futures import ThreadPoolExecutor

from fastapi import Body, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, Response

from . import features, registry, validation
from .cache import TTLCache, cache_key
from .middleware import BodySizeLimitMiddleware, RateLimitMiddleware, RequestLogMiddleware, is_compare_call, is_cubes_call, is_sensitivity_call
from .settings import Settings

log = logging.getLogger("msi.api")
API_VERSION = "0.1.0"
SENS_UNSUPPORTED = "stat values are not modelled for this class yet"


def _json_safe(x):
    """Engine result -> strictly valid JSON values (tuples to lists, NaN / +-inf to null)."""
    if isinstance(x, float):
        return x if math.isfinite(x) else None
    if isinstance(x, dict):
        return {str(k): _json_safe(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_json_safe(v) for v in x]
    return x


def _configure_logging(level):
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(stream=sys.stdout, level=level, format="%(message)s")
    else:
        root.setLevel(level)


def create_app(settings=None):
    settings = settings or Settings.from_env()
    _configure_logging(settings.log_level)
    classes = registry.discover()
    log.info('{"event": "startup", "classes": %s}', list(classes))

    app = FastAPI(title="MapleStory Idle DPS API", version=API_VERSION, docs_url="/api/docs", openapi_url="/api/openapi.json",
                  redoc_url=None)
    app.state.classes = classes
    app.state.settings = settings

    app.state.sens_cache = TTLCache(settings.sens_cache_entries, settings.sens_cache_ttl_s)
    sens_pool = ThreadPoolExecutor(max_workers=settings.sens_workers, thread_name_prefix="sens")
    # cube optimizer: its own pool + result cache; pricing caches (stat rates of a character) shared by cubes / equipment-compare / artifact-potentials
    app.state.cubes_cache = TTLCache(settings.cubes_cache_entries, settings.cubes_cache_ttl_s)
    cubes_pool = ThreadPoolExecutor(max_workers=settings.cubes_workers, thread_name_prefix="cubes")
    pricing = features.PricingService(settings.cubes_cache_ttl_s, rates_entries=32 if settings.cubes_cache_entries else 0,
                                      pricing_entries=16 if settings.cubes_cache_entries else 0)
    app.state.pricing = pricing

    # last added = outermost: log -> CORS -> body limit -> rate limit(s) -> app (429/413 responses still carry CORS headers)
    app.add_middleware(RateLimitMiddleware, limit=settings.rate_limit_compare_per_minute, window_s=settings.rate_limit_burst_window_s,
                       proxy_hops=settings.proxy_hops, match=is_compare_call)
    app.add_middleware(RateLimitMiddleware, limit=settings.rate_limit_cubes_per_minute, window_s=settings.rate_limit_burst_window_s,
                       proxy_hops=settings.proxy_hops, match=is_cubes_call)
    app.add_middleware(RateLimitMiddleware, limit=settings.rate_limit_sens_per_minute, window_s=settings.rate_limit_burst_window_s,
                       proxy_hops=settings.proxy_hops, match=is_sensitivity_call)
    app.add_middleware(RateLimitMiddleware, limit=settings.rate_limit_per_minute, window_s=settings.rate_limit_burst_window_s,
                       proxy_hops=settings.proxy_hops)
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.max_body_bytes)
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_methods=["GET", "POST", "OPTIONS"],
                       allow_headers=["Content-Type"], max_age=600)
    # compress the JSON (schemas ~21 KB, sensitivity ~35 KB): Cloud Run does not gzip for us and egress is the tightest free-tier limit
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(RequestLogMiddleware, proxy_hops=settings.proxy_hops)

    def get_class(class_id):
        entry = classes.get(class_id)
        if entry is None:
            raise HTTPException(status_code=404, detail=f"unknown class {class_id!r}")
        return entry

    @app.exception_handler(RequestValidationError)
    async def on_validation_error(request: Request, exc: RequestValidationError):
        errors = []
        for e in exc.errors():
            loc = [str(p) for p in e.get("loc", ()) if p not in ("body", "query")]
            errors.append({"field": ".".join(loc), "message": e.get("msg", "invalid value")})
        return JSONResponse(status_code=422, content={"detail": "Invalid request", "errors": errors})

    @app.exception_handler(HTTPException)
    async def on_http_error(request: Request, exc: HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(Exception)
    async def on_unexpected(request: Request, exc: Exception):
        rid = request.scope.get("state", {}).get("request_id")
        log.error('{"event": "unhandled", "id": "%s", "error": "%s"}', rid, type(exc).__name__, exc_info=exc)
        return JSONResponse(status_code=500, content={"detail": "internal error", "request_id": rid})

    @app.get("/api/health")
    def health():
        return {"status": "ok", "version": API_VERSION, "classes": len(classes)}

    @app.get("/api/classes")
    def list_classes():
        return {"classes": [c.info() for c in classes.values()]}

    @app.get("/api/classes/{class_id}/schema")
    def class_schema(class_id: str):
        return JSONResponse(_json_safe(get_class(class_id).schema))

    @app.get("/api/classes/{class_id}/defaults")
    def class_defaults(class_id: str, content_type: str | None = Query(default=None, max_length=64)):
        entry = get_class(class_id)
        valid = entry.schema["content_types"]
        if content_type is not None and content_type not in valid:
            return JSONResponse(status_code=422, content={"detail": "Invalid request", "errors": [
                {"field": "content_type", "message": f"must be one of: {', '.join(valid)}"}]})
        return JSONResponse(_json_safe(entry.defaults(content_type)))

    @app.post("/api/classes/{class_id}/compute")
    def class_compute(class_id: str, body: dict = Body(...)):
        entry = get_class(class_id)
        clean, errors = validation.validate_inputs(entry.schema, entry.defaults, body)
        if errors:
            return JSONResponse(status_code=422, content={"detail": "Invalid inputs", "errors": errors})
        try:
            result = entry.compute(clean)
        except Exception as exc:                       # noqa: BLE001 - never leak a stack trace to the client
            log.error('{"event": "compute_failed", "class": "%s"}', class_id, exc_info=exc)
            return JSONResponse(status_code=500, content={"detail": "computation failed for these inputs"})
        return JSONResponse(_json_safe(result))

    @app.get("/api/classes/{class_id}/sensitivity/meta")
    def class_sensitivity_meta(class_id: str):
        entry = get_class(class_id)
        if not entry.supports_sensitivity:
            return JSONResponse(status_code=501, content={"detail": SENS_UNSUPPORTED})
        return JSONResponse(_json_safe(entry.sensitivity_meta()))

    @app.post("/api/classes/{class_id}/sensitivity")
    async def class_sensitivity(class_id: str, body: dict = Body(...)):
        entry = get_class(class_id)
        if not entry.supports_sensitivity:
            return JSONResponse(status_code=501, content={"detail": SENS_UNSUPPORTED})
        compute_body, extras = validation.split_sensitivity_body(body)
        clean, errors = validation.validate_inputs(entry.schema, entry.defaults, compute_body)
        extra_clean, extra_errors = validation.validate_sensitivity_extras(entry.schema, extras, registry.SENSITIVITY_PARTS)
        errors = (errors or []) + extra_errors
        if errors:
            return JSONResponse(status_code=422, content={"detail": "Invalid inputs", "errors": errors})
        which = extra_clean.get("which")
        level = extra_clean.get("companion_comparison_level")
        inputs = dict(clean)
        if "artifact_stars" in extra_clean:
            inputs["artifact_stars"] = extra_clean["artifact_stars"]
        for k in ("companion_levels", "companion_potential_lines_pct"):
            if k in extra_clean:
                inputs[k] = extra_clean[k]
        cache = app.state.sens_cache
        key = cache_key(class_id, clean, extra_clean)
        hit = cache.get(key)
        if hit is not None:
            return Response(content=hit, media_type="application/json", headers={"X-Cache": "HIT"})
        loop = asyncio.get_running_loop()
        try:
            result = await asyncio.wait_for(
                loop.run_in_executor(sens_pool, lambda: entry.sensitivity(inputs, which=which, companion_level=level)),
                timeout=settings.sens_timeout_s)
        except asyncio.TimeoutError:
            log.error('{"event": "sensitivity_timeout", "class": "%s", "timeout_s": %s}', class_id, settings.sens_timeout_s)
            return JSONResponse(status_code=504, content={"detail": f"stat values took longer than {settings.sens_timeout_s} s; try again"})
        except NotImplementedError:
            return JSONResponse(status_code=501, content={"detail": SENS_UNSUPPORTED})
        except Exception as exc:                       # noqa: BLE001 - never leak a stack trace to the client
            log.error('{"event": "sensitivity_failed", "class": "%s"}', class_id, exc_info=exc)
            return JSONResponse(status_code=500, content={"detail": "computation failed for these inputs"})
        payload = json.dumps(_json_safe(result), allow_nan=False, separators=(",", ":")).encode()
        cache.put(key, payload)
        return Response(content=payload, media_type="application/json", headers={"X-Cache": "MISS"})

    # ---- cube optimizer / equipment compare / artifact potentials (FP-Mage only for now: their pricing comes from the sensitivity module) ----------------
    def feature_check(entry, message):
        """501 response when the class (or the engine modules) cannot serve these features, else None (checked before validation, like /sensitivity)."""
        if not entry.supports_sensitivity or not features.available():
            return JSONResponse(status_code=501, content={"detail": message})
        return None

    def invalid(errors):
        return JSONResponse(status_code=422, content={"detail": "Invalid inputs", "errors": errors})

    @app.get("/api/classes/{class_id}/cubes/meta")
    def class_cubes_meta(class_id: str):
        entry = get_class(class_id)
        bad = feature_check(entry, features.CUBES_UNSUPPORTED)
        if bad:
            return bad
        return JSONResponse(_json_safe(dict(features.cubes_meta(), class_id=class_id)))

    async def run_pooled(pool, fn, timeout_s, what, class_id, unsupported):
        """Run ``fn`` in ``pool`` under the request guard: (result, None) or (None, error response)."""
        loop = asyncio.get_running_loop()
        try:
            return await asyncio.wait_for(loop.run_in_executor(pool, fn), timeout=timeout_s), None
        except asyncio.TimeoutError:
            log.error('{"event": "%s_timeout", "class": "%s", "timeout_s": %s}', what.replace(" ", "_"), class_id, timeout_s)
            return None, JSONResponse(status_code=504, content={"detail": f"{what} took longer than {timeout_s} s; try again"})
        except NotImplementedError:
            return None, JSONResponse(status_code=501, content={"detail": unsupported})
        except Exception as exc:                       # noqa: BLE001 - never leak a stack trace to the client
            log.error('{"event": "%s_failed", "class": "%s"}', what.replace(" ", "_"), class_id, exc_info=exc)
            return None, JSONResponse(status_code=500, content={"detail": "computation failed for these inputs"})

    @app.post("/api/classes/{class_id}/cubes")
    async def class_cubes(class_id: str, body: dict = Body(...)):
        entry = get_class(class_id)
        bad = feature_check(entry, features.CUBES_UNSUPPORTED)
        if bad:
            return bad
        compute_body, extras = features.split_body(body, features.CUBES_EXTRA_KEYS)
        clean, errors = validation.validate_inputs(entry.schema, entry.defaults, compute_body)
        gear, only, extra_errors = features.validate_cubes_extras(extras)
        errors = (errors or []) + extra_errors
        if errors:
            return invalid(errors)
        cache = app.state.cubes_cache
        found, missing = features.cubes_lookup(cache, class_id, clean, gear, only)
        if not missing:
            payload = json.dumps(_json_safe(features.cubes_payload(class_id, found)), allow_nan=False, separators=(",", ":")).encode()
            return Response(content=payload, media_type="application/json", headers={"X-Cache": "HIT"})
        fresh, err = await run_pooled(cubes_pool, lambda: features.run_cubes(pricing, entry, clean, gear, missing, cache, class_id), settings.cubes_timeout_s,
                                      "cube optimizer", class_id, features.CUBES_UNSUPPORTED)
        if err:
            return err
        payload = json.dumps(_json_safe(features.cubes_payload(class_id, {**found, **fresh})), allow_nan=False, separators=(",", ":")).encode()
        return Response(content=payload, media_type="application/json", headers={"X-Cache": "PARTIAL" if found else "MISS"})

    async def rates_then(class_id, body, extra_keys, validate_extras, run, unsupported, what):
        """Shared shape of equipment-compare / artifact-potentials: validate, get the character's stat rates (cached, else one sensitivity run in the pool), then
        the cheap engine call inline."""
        entry = get_class(class_id)
        bad = feature_check(entry, unsupported)
        if bad:
            return bad
        compute_body, extras = features.split_body(body, extra_keys)
        clean, errors = validation.validate_inputs(entry.schema, entry.defaults, compute_body)
        parsed, extra_errors = validate_extras(extras)
        errors = (errors or []) + extra_errors
        if errors:
            return invalid(errors)
        if pricing.cached_rates(class_id, clean) is None:
            _, err = await run_pooled(sens_pool, lambda: pricing.rates_context(entry, clean), settings.sens_timeout_s, what, class_id, unsupported)
            if err:
                return err
        try:
            result = run(pricing, entry, clean, parsed)
        except ValueError as exc:
            if str(exc) == "Total DPS is 0":
                return invalid([{"field": "", "message": "Total DPS is 0 for these inputs, so there is nothing to compare against"}])
            log.error('{"event": "%s_failed", "class": "%s"}', what.replace(" ", "_"), class_id, exc_info=exc)
            return JSONResponse(status_code=500, content={"detail": "computation failed for these inputs"})
        except Exception as exc:                       # noqa: BLE001
            log.error('{"event": "%s_failed", "class": "%s"}', what.replace(" ", "_"), class_id, exc_info=exc)
            return JSONResponse(status_code=500, content={"detail": "computation failed for these inputs"})
        return JSONResponse(_json_safe(result))

    @app.post("/api/classes/{class_id}/equipment-compare")
    async def class_equipment_compare(class_id: str, body: dict = Body(...)):
        return await rates_then(class_id, body, features.EQUIPMENT_EXTRA_KEYS, features.validate_equipment_extras,
                                lambda svc, entry, clean, parsed: features.run_equipment(svc, entry, clean, parsed[0], parsed[1]),
                                features.EQUIPMENT_UNSUPPORTED, "equipment compare")

    @app.post("/api/classes/{class_id}/artifact-potentials")
    async def class_artifact_potentials(class_id: str, body: dict = Body(...)):
        return await rates_then(class_id, body, features.POTENTIALS_EXTRA_KEYS, features.validate_potentials_extras,
                                lambda svc, entry, clean, parsed: features.run_potentials(svc, entry, clean, parsed),
                                features.POTENTIALS_UNSUPPORTED, "artifact potentials")

    return app


app = create_app()
