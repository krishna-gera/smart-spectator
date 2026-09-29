#!/usr/bin/env python3
"""
Generate small controlled synthetic test samples for Phase 2 evaluation.
Creates test images containing geometric representations of:
- person
- bottle
- chair
- laptop
- phone
"""

import json
from pathlib import Path
import cv2
import numpy as np

SAMPLES_DIR = Path(__file__).resolve().parent / "samples"
SAMPLES_DIR.mkdir(parents=True, exist_ok=True)


def create_sample_images():
    annotations = {}

    # Sample 1: Person + Phone
    img1 = np.full((720, 1280, 3), (240, 240, 240), dtype=np.uint8)
    # Draw person: head (circle), body (rect), legs (lines)
    cv2.circle(img1, (400, 220), 45, (60, 60, 180), -1)  # Head
    cv2.rectangle(img1, (340, 265), (460, 500), (80, 120, 200), -1)  # Torso
    cv2.rectangle(img1, (350, 500), (395, 660), (40, 40, 60), -1)  # Leg 1
    cv2.rectangle(img1, (405, 500), (450, 660), (40, 40, 60), -1)  # Leg 2
    # Phone in hand
    cv2.rectangle(img1, (470, 360), (510, 430), (30, 30, 30), -1)
    cv2.imwrite(str(SAMPLES_DIR / "sample_person_phone.jpg"), img1)

    annotations["sample_person_phone.jpg"] = [
        {"class_name": "person", "bbox_xyxy": [330 / 1280, 170 / 720, 470 / 1280, 670 / 720]},
        {"class_name": "cell phone", "bbox_xyxy": [465 / 1280, 355 / 720, 515 / 1280, 435 / 720]}
    ]

    # Sample 2: Laptop + Bottle on desk
    img2 = np.full((720, 1280, 3), (230, 230, 235), dtype=np.uint8)
    # Desk
    cv2.rectangle(img2, (100, 480), (1180, 700), (140, 160, 180), -1)
    # Laptop screen & base
    cv2.rectangle(img2, (450, 260), (750, 480), (50, 50, 50), -1)
    cv2.rectangle(img2, (400, 480), (800, 520), (100, 100, 100), -1)
    # Bottle
    cv2.rectangle(img2, (880, 360), (950, 500), (180, 120, 60), -1)
    cv2.rectangle(img2, (900, 330), (930, 360), (200, 150, 80), -1)
    cv2.imwrite(str(SAMPLES_DIR / "sample_laptop_bottle.jpg"), img2)

    annotations["sample_laptop_bottle.jpg"] = [
        {"class_name": "laptop", "bbox_xyxy": [390 / 1280, 250 / 720, 810 / 1280, 530 / 720]},
        {"class_name": "bottle", "bbox_xyxy": [870 / 1280, 320 / 720, 960 / 1280, 510 / 720]}
    ]

    # Sample 3: Chair
    img3 = np.full((720, 1280, 3), (245, 245, 245), dtype=np.uint8)
    # Chair backrest, seat, legs
    cv2.rectangle(img3, (520, 200), (760, 420), (90, 80, 160), -1)
    cv2.rectangle(img3, (480, 420), (800, 480), (110, 100, 180), -1)
    cv2.line(img3, (510, 480), (510, 680), (40, 40, 40), 8)
    cv2.line(img3, (770, 480), (770, 680), (40, 40, 40), 8)
    cv2.imwrite(str(SAMPLES_DIR / "sample_chair.jpg"), img3)

    annotations["sample_chair.jpg"] = [
        {"class_name": "chair", "bbox_xyxy": [470 / 1280, 190 / 720, 810 / 1280, 690 / 720]}
    ]

    # Write annotations file
    with open(SAMPLES_DIR / "annotations.json", "w") as f:
        json.dump(annotations, f, indent=2)

    print(f"Created {len(annotations)} test samples in '{SAMPLES_DIR}'")


if __name__ == "__main__":
    create_sample_images()
