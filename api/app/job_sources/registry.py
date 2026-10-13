from app.job_sources.adapters import JobSourceAdapter
from app.job_sources.schemas import SourceCapability


class SourceCapabilityRegistry:
    """In-memory foundation; replace with reviewed persisted configurations later."""

    def __init__(self) -> None:
        self._sources: dict[str, SourceCapability] = {}
        self._adapters: dict[str, JobSourceAdapter] = {}

    def register(self, source: SourceCapability) -> None:
        self._sources[source.source_name.casefold()] = source

    def register_adapter(self, adapter: JobSourceAdapter) -> None:
        capability = adapter.get_capabilities()
        self.register(capability)
        self._adapters[capability.source_name.casefold()] = adapter

    def get(self, source_name: str) -> SourceCapability:
        return self._sources[source_name.casefold()]

    def list(self) -> tuple[SourceCapability, ...]:
        return tuple(self._sources.values())

    def get_adapter(self, source_name: str) -> JobSourceAdapter:
        return self._adapters[source_name.casefold()]


source_registry = SourceCapabilityRegistry()
