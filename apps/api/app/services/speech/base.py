from abc import ABC, abstractmethod
from collections.abc import AsyncIterator


class TranscriptionProviderError(Exception):
    """Raised for both configuration problems (no key set) and runtime/connection failures."""


class TranscriptionProvider(ABC):
    name: str

    @abstractmethod
    def stream(self, audio: AsyncIterator[bytes]) -> AsyncIterator[str]:
        """Takes raw PCM16 mono audio frames, yields finalized transcript segments as they
        become available. Raises TranscriptionProviderError on failure."""
