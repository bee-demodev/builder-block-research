import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from labeler.vision_labeler import select_setup_quality_autolabels

packet = {
    "items": [
        {
            "example_id": "dense::good",
            "candidate_detections": [{"class_id": 3, "bbox": [0.5, 0.5, 0.2, 0.2]}],
            "recommended_action": "accept",
            "setup_type": "high_probability_long",
            "setup_confidence": 0.91,
        },
        {
            "example_id": "dense::bad",
            "candidate_detections": [],
            "recommended_action": "no_setup",
            "setup_type": "invalid_chop",
            "setup_confidence": 0.87,
        },
    ]
}

print(
    select_setup_quality_autolabels(
        packet,
        existing_answer_ids=set(),
        max_new_items=10,
        positive_confidence_floor=0.72,
        negative_confidence_floor=0.78,
    )
)
