# Spatial Zone System & Polygon Geometry
## Multi-Camera Region-of-Interest & Dwell Tracking

---

### 1. Geometric Model

Zones are defined as arbitrary convex or concave polygons with normalized coordinates:
$$x, y \in [0.0, 1.0]$$

Normalized coordinates decouple zone definitions from camera resolutions, frame rotations, and client display viewports.

---

### 2. Ray-Casting Point-in-Polygon Algorithm

Centroid testing uses the classic Jordan Curve ray-casting algorithm (`services/event_engine/zones.py:point_inside_polygon`):

```python
def point_inside_polygon(point: Tuple[float, float], polygon: List[List[float]]) -> bool:
    x, y = point
    n = len(polygon)
    inside = False
    p1x, p1y = polygon[0]
    for i in range(1, n + 1):
        p2x, p2y = polygon[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y
    return inside
```

---

### 3. Track Centroid Calculation

Track bounding boxes are represented as normalized coordinates $[x_{min}, y_{min}, x_{max}, y_{max}]$.
The centroid is computed as:
$$c_x = \frac{x_{min} + x_{max}}{2}, \quad c_y = \frac{y_{min} + y_{max}}{2}$$

---

### 4. Dwell Time & Loitering Detection

The `ZoneEngine` tracks state per tuple `(camera_id, zone_id, track_id)`:
1. **Entry (`ZONE_ENTER`):** Emitted on the first frame where the centroid intersects the polygon.
2. **Dwell Duration:** Computed as:
   $$\text{dwell} = t_{\text{last\_seen}} - t_{\text{entry}}$$
3. **Loitering Detection (`ZONE_LOITERING`):** When `dwell >= loitering_threshold_seconds` (default: 30s) and the object class is `person`.
4. **Exit (`ZONE_EXIT`):** Emitted when a track leaves the polygon or is lost for $> 1.0$s grace period. Total dwell time is logged.
