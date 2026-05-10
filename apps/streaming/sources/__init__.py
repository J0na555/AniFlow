from __future__ import annotations

import importlib
import inspect
import pkgutil
import re
from functools import lru_cache

from apps.streaming.models import StreamingSource

from .base_source import StreamingSourceAdapter
from .crunchyroll_source import CrunchyrollSourceAdapter
from .gogoanime_source import GogoanimeSourceAdapter
from .template_source import TemplateSourceAdapter


def _normalize_source_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower().strip())


@lru_cache(maxsize=1)
def _adapter_registry() -> dict[str, type[StreamingSourceAdapter]]:
    registry: dict[str, type[StreamingSourceAdapter]] = {}

    for module_info in sorted(pkgutil.iter_modules(__path__), key=lambda info: info.name):
        module_name = module_info.name
        if module_name in {"base_source", "template_source"}:
            continue

        try:
            module = importlib.import_module(f"{__name__}.{module_name}")
        except Exception:
            continue

        for _, adapter_cls in inspect.getmembers(module, inspect.isclass):
            if not issubclass(adapter_cls, StreamingSourceAdapter):
                continue
            if adapter_cls in {StreamingSourceAdapter, TemplateSourceAdapter}:
                continue
            if adapter_cls.__module__ != module.__name__:
                continue

            normalized_names = {
                _normalize_source_name(alias)
                for alias in getattr(adapter_cls, "source_names", ())
                if alias
            }
            if not normalized_names:
                inferred_name = adapter_cls.__name__.removesuffix("SourceAdapter")
                normalized_names.add(_normalize_source_name(inferred_name))

            for normalized_name in normalized_names:
                registry.setdefault(normalized_name, adapter_cls)

    return registry


def get_adapter_for_source(source: StreamingSource) -> StreamingSourceAdapter:
    adapter_cls = _adapter_registry().get(_normalize_source_name(source.name))
    if adapter_cls is None:
        return TemplateSourceAdapter(source)
    return adapter_cls(source)


__all__ = [
    "CrunchyrollSourceAdapter",
    "GogoanimeSourceAdapter",
    "StreamingSourceAdapter",
    "TemplateSourceAdapter",
    "get_adapter_for_source",
]
