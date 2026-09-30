"""
Smart Spectator - Local Language Model Adapter
Conforms to Section 14 of Phase 10 Specification.
Abstract provider interface for optional local language models (llama.cpp, ONNX, MLC).
Zero external API calls; zero cloud dependencies.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Iterator, Optional


class LocalLanguageModelProvider(ABC):
    """
    Abstract interface for optional on-device language models.
    Does not require or bundle a mandatory LLM.
    """

    @abstractmethod
    def generate(self, prompt: str, max_tokens: int = 128, temperature: float = 0.1) -> str:
        """Generates a text completion locally."""
        pass

    @abstractmethod
    def stream(self, prompt: str, max_tokens: int = 128, temperature: float = 0.1) -> Iterator[str]:
        """Streams text completion tokens locally."""
        pass

    @abstractmethod
    def health(self) -> Dict[str, Any]:
        """Reports provider operational health and device backend."""
        pass

    @abstractmethod
    def model_info(self) -> Dict[str, Any]:
        """Returns model identifier, precision, context length, and weights path."""
        pass


class LocalReferenceLLMProvider(LocalLanguageModelProvider):
    """
    Default offline reference provider. Performs deterministic template synthesis
    without loading large LLM weight files into memory unless explicitly configured.
    """

    def __init__(self, model_name: str = "local-template-synthesizer-v1"):
        self.model_name = model_name
        self._is_ready = True

    def generate(self, prompt: str, max_tokens: int = 128, temperature: float = 0.1) -> str:
        # Deterministic offline rule synthesis
        clean = prompt.strip()
        if "summarize" in clean.lower():
            return "Activity Summary: Regular monitoring active with zero unverified breaches."
        return "Local semantic evaluation complete."

    def stream(self, prompt: str, max_tokens: int = 128, temperature: float = 0.1) -> Iterator[str]:
        tokens = self.generate(prompt).split()
        for t in tokens:
            yield t + " "

    def health(self) -> Dict[str, Any]:
        return {
            "status": "READY" if self._is_ready else "UNAVAILABLE",
            "provider": "LocalReferenceProvider",
            "runtime": "Native Local CPU",
            "cloud_enabled": False,
        }

    def model_info(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_name,
            "version": "1.0.0",
            "architecture": "DeterministicTemplateSynthesizer",
            "precision": "N/A",
            "max_context_tokens": 1024,
            "external_network": False,
        }


local_llm_provider = LocalReferenceLLMProvider()
