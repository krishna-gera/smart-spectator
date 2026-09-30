"""
Smart Spectator - Local AI Model Orchestrator
Conforms to Section 15 of Phase 10 Specification.
Routes incoming perceptual and analytical tasks to specialized local models.
Never permits direct unvalidated execution.
"""

from typing import Dict, Any, Optional

from ai.orchestration.llm_adapter import local_llm_provider
from ai.orchestration.safety import action_safety_validator
from services.hub_backend.query.interpreter import query_interpreter


class AIOrchestrator:
    """
    Coordinates local edge AI tasks: detection, tracking, temporal classification,
    statistical anomaly detection, and semantic query parsing.
    """

    def classify_task(self, input_data: Dict[str, Any]) -> str:
        """Classifies the task type based on input payload structure."""
        if "frame" in input_data or "image" in input_data:
            return "SPATIAL_DETECTION"
        elif "trajectory" in input_data or "features" in input_data:
            return "TEMPORAL_SEQUENCE"
        elif "observed_count" in input_data and "hour" in input_data:
            return "ANOMALY_EVALUATION"
        elif "natural_query" in input_data or "query_text" in input_data:
            return "QUERY_INTERPRETATION"
        return "SEMANTIC_SYNTHESIS"

    def orchestrate(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        task_type = self.classify_task(input_data)

        if task_type == "QUERY_INTERPRETATION":
            text = input_data.get("natural_query") or input_data.get("query_text", "")
            sq = query_interpreter.interpret(text)
            return {"task": task_type, "status": "COMPLETED", "result": sq.to_dict()}

        elif task_type == "SEMANTIC_SYNTHESIS":
            prompt = input_data.get("prompt", "Summarize recent activity.")
            summary = local_llm_provider.generate(prompt)
            return {"task": task_type, "status": "COMPLETED", "result": {"summary": summary}}

        return {
            "task": task_type,
            "status": "DELEGATED_TO_PIPELINE",
            "message": f"Task '{task_type}' is handled by dedicated real-time pipeline workers."
        }


ai_orchestrator = AIOrchestrator()
