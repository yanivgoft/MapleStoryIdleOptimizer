"""Shared by the API tests that need a class WITHOUT stat values (the 501 contract): the first class the registry reports as unsupported; once every class is ported,
``night_lord`` with the engine's capability check (``sensitivity.supports``, what ``api.registry`` asks) patched off for the duration of the test."""
from api import registry
from engine import sensitivity


def unsupported_class(monkeypatch, victim="night_lord"):
    for cid, entry in registry.discover().items():
        if not entry.supports_sensitivity:
            return cid
    real = sensitivity.supports
    monkeypatch.setattr(sensitivity, "supports", lambda m: False if getattr(m, "CLASS_ID", None) == victim else real(m))
    return victim
