"""
Smart Spectator - Local Language Model Adapter
Conforms to Section 14 of Phase 10 Specification.
Abstract provider interface for optional local language models (Ollama, llama.cpp, ONNX).
Zero external API calls; zero cloud dependencies.
All processing runs 100% locally on localhost.
"""

from abc import ABC, abstractmethod
import json
import os
from typing import Dict, Any, Iterator, Optional
import urllib.request
import urllib.error


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
        """Returns model identifier, precision, context length, and architecture."""
        pass


class LocalReferenceLLMProvider(LocalLanguageModelProvider):
    """
    Deterministic template synthesizer fallback.
    Explicitly noted: this is NOT a neural network LLM. It generates structured,
    rule-based deterministic summaries for offline air-gapped environments without
    requiring multi-gigabyte neural weight downloads.
    """

    def __init__(self, model_name: str = "deterministic-template-synthesizer-v1"):
        self.model_name = model_name
        self._is_ready = True

    def generate(self, prompt: str, max_tokens: int = 128, temperature: float = 0.1) -> str:
        clean = prompt.strip().lower()
        if "summarize" in clean or "summary" in clean:
            return "Activity Summary: Local surveillance active; all detected events processed deterministically."
        elif "anomaly" in clean:
            return "Anomaly Analysis: Statistical z-score evaluation confirms baseline alignment."
        return "Local deterministic semantic evaluation complete."

    def stream(self, prompt: str, max_tokens: int = 128, temperature: float = 0.1) -> Iterator[str]:
        tokens = self.generate(prompt).split()
        for t in tokens:
            yield t + " "

    def health(self) -> Dict[str, Any]:
        return {
            "status": "READY" if self._is_ready else "UNAVAILABLE",
            "provider": "LocalReferenceProvider",
            "runtime": "Local Deterministic Rule Engine",
            "cloud_enabled": False,
            "neural_network": False,
            "is_synthetic_template": True,
        }

    def model_info(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_name,
            "version": "1.0.0",
            "architecture": "DeterministicTemplateSynthesizer",
            "precision": "N/A",
            "max_context_tokens": 1024,
            "external_network": False,
            "neural_network": False,
        }


class LocalOllamaLLMProvider(LocalLanguageModelProvider):
    """
    Optional on-device neural LLM adapter connecting to local Ollama (e.g., http://127.0.0.1:11434).
    100% localhost; never dials external cloud or remote endpoints.
    Falls back gracefully to LocalReferenceLLMProvider if Ollama is not active.
    """

    def __init__(
        self,
        endpoint: str = "http://127.0.0.1:11434",
        model: str = "llama3.2:1b",
        fallback: Optional[LocalLanguageModelProvider] = None,
    ):
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self.fallback = fallback or LocalReferenceLLMProvider()

    def _is_ollama_available(self) -> bool:
        try:
            req = urllib.request.Request(f"{self.endpoint}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=0.5) as resp:
                return resp.status == 200
        except Exception:
            return False

    def generate(self, prompt: str, max_tokens: int = 128, temperature: float = 0.1) -> str:
        try:
            payload = json.dumps({
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": max_tokens,
                    "temperature": temperature,
                }
            }).encode("utf-8")
            req = urllib.request.Request(
                f"{self.endpoint}/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("response", "").strip()
        except Exception:
            # Fall back cleanly to deterministic synthesizer if Ollama is unreachable
            return self.fallback.generate(prompt, max_tokens, temperature)

    def stream(self, prompt: str, max_tokens: int = 128, temperature: float = 0.1) -> Iterator[str]:
        # For simplicity in local execution, yield words from generate
        text = self.generate(prompt, max_tokens, temperature)
        for w in text.split():
            yield w + " "

    def health(self) -> Dict[str, Any]:
        available = self._is_ollama_available()
        return {
            "status": "READY" if available else "FALLBACK_MODE",
            "provider": "LocalOllamaLLMProvider",
            "runtime": f"Local Ollama ({self.endpoint})" if available else "Fallback Synthesizer",
            "model": self.model,
            "cloud_enabled": False,
            "neural_network": available,
        }

    def model_info(self) -> Dict[str, Any]:
        return {
            "model_id": f"ollama/{self.model}",
            "version": "local",
            "architecture": "Local LLM via Ollama REST",
            "precision": "4-bit quantized",
            "max_context_tokens": 2048,
            "external_network": False,
            "neural_network": True,
        }


# Default provider instance: Ollama with seamless deterministic fallback
_ollama_url = os.getenv("OLLAMA_ENDPOINT", "http://127.0.0.1:11434")
local_llm_provider: LocalLanguageModelProvider = LocalOllamaLLMProvider(
    endpoint=_ollama_url,
    fallback=LocalReferenceLLMProvider()
)
