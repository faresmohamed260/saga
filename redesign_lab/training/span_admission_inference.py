"""Inference helpers for frozen span-admission classifiers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Sequence

import numpy as np
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from redesign_lab.training.span_admission_transformer import row_to_model_text

PERSON_LABELS = {
    "CANDIDATE_PERSON_NAME",
    "HONORIFIC_PERSON_NAME",
    "DESCRIPTIVE_PERSON_REFERENCE",
    "RELATION_PERSON_REFERENCE",
    "GROUP_PERSON_REFERENCE",
    "PRONOUN_REFERENCE",
}
PERSON_ADMISSION_LABELS = PERSON_LABELS - {"PRONOUN_REFERENCE"}
NON_PERSON_LABELS = {"LOCATION", "ORGANIZATION", "NON_PERSON_MISC", "MALFORMED_OR_NOISE"}


@dataclass
class FrozenSpanAdmissionClassifier:
    model: Any
    tokenizer: Any
    labels: List[str]
    label_to_id: Dict[str, int]
    device: torch.device

    @classmethod
    def load(cls, model_root: str | Path) -> "FrozenSpanAdmissionClassifier":
        model_path = Path(model_root)
        label_map_path = model_path / "label_map.json"
        payload = json.loads(label_map_path.read_text(encoding="utf-8"))
        label_to_id = {label: int(idx) for label, idx in payload["label_to_id"].items()}
        id_to_label = {int(idx): label for idx, label in payload["id_to_label"].items()}
        labels = [id_to_label[idx] for idx in sorted(id_to_label)]
        tokenizer = AutoTokenizer.from_pretrained(model_path)
        model = AutoModelForSequenceClassification.from_pretrained(model_path)
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model.to(device)
        model.eval()
        return cls(model=model, tokenizer=tokenizer, labels=labels, label_to_id=label_to_id, device=device)

    def predict(self, rows: Sequence[Dict[str, Any]], *, batch_size: int = 32) -> List[Dict[str, Any]]:
        predicted: List[Dict[str, Any]] = []
        for start in range(0, len(rows), batch_size):
            batch = rows[start : start + batch_size]
            enc = self.tokenizer(
                [row["model_text"] for row in batch],
                truncation=True,
                padding=True,
                max_length=256,
                return_tensors="pt",
            )
            enc = {key: value.to(self.device) for key, value in enc.items()}
            with torch.no_grad():
                logits = self.model(**enc).logits
                probs = torch.softmax(logits, dim=-1).cpu().numpy()
            for row, prob in zip(batch, probs):
                pred_idx = int(np.argmax(prob))
                pred_label = self.labels[pred_idx]
                predicted.append(
                    {
                        **row,
                        "predicted_label": pred_label,
                        "predicted_confidence": float(prob[pred_idx]),
                        "predicted_group": "person" if pred_label in PERSON_LABELS else "non_person",
                        "probabilities": {label: float(prob[idx]) for idx, label in enumerate(self.labels)},
                    }
                )
        return predicted


def infer_span_admission_features(mention_text: str, full_text: str, start_char: int) -> Dict[str, Any]:
    tokens = [token for token in (mention_text or "").split() if token]
    lower = (mention_text or "").lower()
    return {
        "is_capitalized": bool((mention_text or "").strip()[:1].isupper()),
        "is_multi_token": len(tokens) >= 2,
        "has_honorific": lower.startswith(
            ("mr", "mrs", "miss", "ms", "dr", "sir", "lady", "lord", "captain", "professor", "reverend", "parson")
        ),
        "in_quote": full_text[: max(0, start_char)].count('"') % 2 == 1 or full_text[: max(0, start_char)].count("â€œ") % 2 == 1,
        "has_possessive": "'s" in (mention_text or "") or "â€™s" in (mention_text or ""),
        "locative_suffix": lower.rstrip(".").endswith(
            (" lane", " street", " road", " avenue", " hall", " house", " court", " square", " park", " inn", " bridge", " gate", " station")
        ),
    }


def build_span_admission_row(
    *,
    span_text: str,
    sentence: str,
    left_context: str,
    right_context: str,
    features: Dict[str, Any],
) -> Dict[str, Any]:
    row = {
        "span_text": span_text,
        "sentence": sentence,
        "left_context": left_context,
        "right_context": right_context,
        "features": features,
    }
    row["model_text"] = row_to_model_text(row)
    return row
