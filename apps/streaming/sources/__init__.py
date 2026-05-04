from __future__ import annotations

from apps.streaming.models import StreamingSource

from .base_source import StreamingSourceAdapter
from .crunchyroll_source import CrunchyrollSourceAdapter
from .gogoanime_source import GogoanimeSourceAdapter
from .template_source import TemplateSourceAdapter


def get_adapter_for_source(source: StreamingSource) -> StreamingSourceAdapter:
    source_name = source.name.lower().strip()
    if source_name == "crunchyroll":
        return CrunchyrollSourceAdapter(source)
    if source_name in {"gogoanime", "gogo anime", "anitaku", "ani taku"}:
        return GogoanimeSourceAdapter(source)
    return TemplateSourceAdapter(source)


__all__ = [
    "CrunchyrollSourceAdapter",
    "GogoanimeSourceAdapter",
    "StreamingSourceAdapter",
    "TemplateSourceAdapter",
    "get_adapter_for_source",
]
