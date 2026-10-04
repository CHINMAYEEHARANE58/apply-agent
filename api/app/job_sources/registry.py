from app.job_sources.schemas import SourceCapability


class SourceCapabilityRegistry:
    """In-memory foundation; replace with reviewed persisted configurations later."""

    def __init__(self) -> None:
        self._sources: dict[str, SourceCapability] = {}

    def register(self, source: SourceCapability) -> None:
        self._sources[source.source_name.casefold()] = source

    def get(self, source_name: str) -> SourceCapability:
        return self._sources[source_name.casefold()]

    def list(self) -> tuple[SourceCapability, ...]:
        return tuple(self._sources.values())


source_registry = SourceCapabilityRegistry()
