"""
Smart Spectator - Level 1 YOLO Object Detector
Conforms to shared/protocols/ai_models.py and shared/schemas/v1/models.py
"""

import os
import time
import uuid
from typing import List, Dict, Any, Tuple, Optional
import numpy as np
import cv2

from shared.protocols.ai_models import ObjectDetector
from shared.schemas.v1.models import Detection, ModelMetadata, HardwareBackend
from ai.inference.manager import provider_manager, BaseORTInferenceProvider

COCO_CLASSES = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat",
    "traffic light", "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat",
    "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe", "backpack",
    "umbrella", "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball",
    "kite", "baseball bat", "baseball glove", "skateboard", "surfboard", "tennis racket",
    "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple",
    "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair",
    "couch", "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse",
    "remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink", "refrigerator",
    "book", "clock", "vase", "scissors", "teddy bear", "hair drier", "toothbrush"
]


class YOLOObjectDetector(ObjectDetector):
    """
    Level 1 Spatial Object Detector using YOLOv8 ONNX architecture.
    Produces standardized, normalized Detection schemas.
    """

    def __init__(
        self,
        model_id: str = "yolov8n",
        model_path: str = "ai/models/yolov8n.onnx",
        input_size: Tuple[int, int] = (640, 640),
        confidence_threshold: float = 0.35,
        iou_threshold: float = 0.45
    ):
        self.model_id = model_id
        self.model_path = model_path
        self.input_size = input_size
        self.confidence_threshold = confidence_threshold
        self.iou_threshold = iou_threshold
        self.provider: Optional[BaseORTInferenceProvider] = None
        self.backend: HardwareBackend = HardwareBackend.CPU
        self.is_loaded = False
        self.classes = COCO_CLASSES
        self.last_metrics: Dict[str, float] = {}

    def load(self, weights_path: Optional[str] = None, provider: Optional[Any] = None) -> bool:
        target_path = weights_path or self.model_path
        if provider is None:
            req_provider = os.getenv("AI_PROVIDER", "auto")
            backend, prov = provider_manager.get_preferred_provider(req_provider)
            self.backend = backend
            self.provider = prov
        elif isinstance(provider, str):
            backend, prov = provider_manager.get_preferred_provider(provider)
            self.backend = backend
            self.provider = prov
        else:
            self.provider = provider
            self.backend = getattr(provider, "backend", HardwareBackend.CPU)

        if not self.provider.initialize({}):
            return False

        loaded = self.provider.load_model(self.model_id, target_path, self.backend)
        self.is_loaded = loaded
        return loaded

    def unload(self) -> None:
        if self.provider and self.is_loaded:
            self.provider.unload_model(self.model_id)
            self.is_loaded = False

    def preprocess(self, frame: np.ndarray) -> Tuple[np.ndarray, float, Tuple[int, int]]:
        """Letterbox resize to 640x640 maintaining aspect ratio."""
        h, w = frame.shape[:2]
        target_w, target_h = self.input_size
        scale = min(target_w / w, target_h / h)
        new_w, new_h = int(w * scale), int(h * scale)

        resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        canvas = np.full((target_h, target_w, 3), 114, dtype=np.uint8)
        
        pad_x = (target_w - new_w) // 2
        pad_y = (target_h - new_h) // 2
        canvas[pad_y : pad_y + new_h, pad_x : pad_x + new_w] = resized

        # BGR to RGB, Normalize [0, 1], CHW layout
        blob = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        blob = np.transpose(blob, (2, 0, 1))
        blob = np.expand_dims(blob, axis=0) # [1, 3, 640, 640]

        return blob, scale, (pad_x, pad_y)

    def postprocess(
        self,
        raw_output: np.ndarray,
        orig_shape: Tuple[int, int],
        scale: float,
        pad: Tuple[int, int],
        confidence_threshold: float
    ) -> List[Detection]:
        """
        Parses YOLOv8 output tensor [1, 84, 8400].
        84 = [cx, cy, w, h] + 80 class probabilities.
        Converts to normalized [x_min, y_min, x_max, y_max] in [0.0, 1.0].
        """
        orig_h, orig_w = orig_shape
        pad_x, pad_y = pad

        # Squeeze batch dimension -> [84, 8400] -> Transpose to [8400, 84]
        predictions = np.squeeze(raw_output)
        if predictions.shape[0] == 84:
            predictions = np.transpose(predictions, (1, 0))

        boxes = predictions[:, :4]
        scores = predictions[:, 4:]
        class_ids = np.argmax(scores, axis=1)
        confidences = np.max(scores, axis=1)

        mask = confidences >= confidence_threshold
        boxes = boxes[mask]
        class_ids = class_ids[mask]
        confidences = confidences[mask]

        if len(boxes) == 0:
            return []

        # Convert [cx, cy, w, h] in 640x640 canvas to corner coordinates [x1, y1, x2, y2]
        cx, cy, w, h = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
        x1 = cx - w / 2 - pad_x
        y1 = cy - h / 2 - pad_y
        x2 = cx + w / 2 - pad_x
        y2 = cy + h / 2 - pad_y

        # Unscale back to original image pixel coordinates
        x1 = np.clip(x1 / scale, 0, orig_w)
        y1 = np.clip(y1 / scale, 0, orig_h)
        x2 = np.clip(x2 / scale, 0, orig_w)
        y2 = np.clip(y2 / scale, 0, orig_h)

        # Apply OpenCV NMSBoxes
        nms_boxes = [[int(x1[i]), int(y1[i]), int(x2[i] - x1[i]), int(y2[i] - y1[i])] for i in range(len(boxes))]
        indices = cv2.dnn.NMSBoxes(nms_boxes, confidences.tolist(), confidence_threshold, self.iou_threshold)

        detections: List[Detection] = []
        if len(indices) > 0:
            for idx in indices.flatten():
                c_id = int(class_ids[idx])
                c_name = self.classes[c_id] if c_id < len(self.classes) else f"class_{c_id}"
                conf = float(confidences[idx])
                
                # Normalize coordinates strictly to [0.0, 1.0] as required by SS-DOC-008
                norm_box = [
                    float(round(x1[idx] / orig_w, 4)),
                    float(round(y1[idx] / orig_h, 4)),
                    float(round(x2[idx] / orig_w, 4)),
                    float(round(y2[idx] / orig_h, 4)),
                ]
                
                detections.append(
                    Detection(
                        detection_id=f"det_{uuid.uuid4().hex[:8]}",
                        class_id=c_id,
                        class_name=c_name,
                        confidence=round(conf, 3),
                        bbox_xyxy=norm_box,
                        attributes={"raw_pixel_box": [int(x1[idx]), int(y1[idx]), int(x2[idx]), int(y2[idx])]}
                    )
                )

        return detections

    def detect(self, frame: np.ndarray, confidence_threshold: Optional[float] = None) -> List[Detection]:
        if not self.is_loaded or self.provider is None:
            return []

        t0 = time.perf_counter()
        conf_thresh = confidence_threshold or self.confidence_threshold
        orig_h, orig_w = frame.shape[:2]

        blob, scale, pad = self.preprocess(frame)
        t_pre = (time.perf_counter() - t0) * 1000.0

        t1 = time.perf_counter()
        input_name = self.provider.model_metadata[self.model_id]["inputs"][0]
        preds = self.provider.predict(self.model_id, {input_name: blob})
        output_name = self.provider.model_metadata[self.model_id]["outputs"][0]
        raw_output = preds[output_name]
        t_inf = (time.perf_counter() - t1) * 1000.0

        t2 = time.perf_counter()
        detections = self.postprocess(raw_output, (orig_h, orig_w), scale, pad, conf_thresh)
        t_post = (time.perf_counter() - t2) * 1000.0
        t_tot = (time.perf_counter() - t0) * 1000.0

        self.last_metrics = {
            "preprocess_ms": round(t_pre, 2),
            "inference_ms": round(t_inf, 2),
            "postprocess_ms": round(t_post, 2),
            "total_ms": round(t_tot, 2)
        }
        return detections

    def batch_detect(self, frames: List[np.ndarray], confidence_threshold: float = 0.35) -> List[List[Detection]]:
        return [self.detect(f, confidence_threshold) for f in frames]

    def get_metadata(self) -> ModelMetadata:
        perf = self.get_performance()
        return ModelMetadata(
            model_id=self.model_id,
            name="YOLOv8-Nano Object Detector",
            version="8.0.0",
            task_type="detection",
            format="onnx",
            input_resolution=[1, 3, self.input_size[0], self.input_size[1]],
            mean_inference_latency_ms=perf.get("mean_ms", 0.0),
            current_backend=self.backend,
            supports_npu=(self.backend == HardwareBackend.NPU_QNN),
            weights_path=getattr(self.provider, "model_metadata", {}).get(self.model_id, {}).get("path", "ai/models/yolov8n.onnx"),
            checksum_sha256="default"
        )

    def get_performance(self) -> Dict[str, float]:
        if self.provider:
            return self.provider.get_performance(self.model_id)
        return {"mean_ms": 0.0, "p50_ms": 0.0, "p95_ms": 0.0, "fps": 0.0}
