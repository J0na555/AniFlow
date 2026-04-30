from __future__ import annotations

from apps.streaming.models import StreamingSource

from .base_source import StreamingSourceAdapter
from .crunchyroll_source import CrunchyrollSourceAdapter
from .template_source import TemplateSourceAdapter


def get_adapter_for_source(source: StreamingSource) -> StreamingSourceAdapter:
    if source.name.lower() == "crunchyroll":
        return CrunchyrollSourceAdapter(source)
    return TemplateSourceAdapter(source)


__all__ = [
    "CrunchyrollSourceAdapter",
    "StreamingSourceAdapter",
    "TemplateSourceAdapter",
    "get_adapter_for_source",
]
