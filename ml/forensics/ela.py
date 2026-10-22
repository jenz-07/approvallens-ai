"""Error-level-analysis baseline (OpenCV). Experimental, unvalidated: no accuracy claim is made."""
from __future__ import annotations
import numpy as np, cv2


def ela_score(img_bgr: np.ndarray, quality: int = 90) -> dict:
    ok, enc = cv2.imencode(".jpg", img_bgr, [cv2.IMWRITE_JPEG_QUALITY, quality])
    rec = cv2.imdecode(enc, cv2.IMREAD_COLOR)
    diff = np.abs(img_bgr.astype(np.int16) - rec.astype(np.int16)).mean(axis=2)
    h, w = diff.shape; bs = 32
    blocks = [diff[y:y + bs, x:x + bs].mean() for y in range(0, h - bs + 1, bs) for x in range(0, w - bs + 1, bs)]
    blocks = np.array(blocks) if blocks else np.array([0.0])
    return {"mean_error": float(diff.mean()), "block_error_std": float(blocks.std()), "max_block_error": float(blocks.max()),
            "label": "experimental_visual_anomaly_signal", "disclaimer": "Does not authenticate documents or establish fraud."}
