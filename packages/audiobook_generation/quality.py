"""Text/audio alignment metrics for audiobook quality decisions."""

from __future__ import annotations

import re


def normalized_words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", str(text or "").lower())


def word_error_rate(reference: str, hypothesis: str) -> float:
    expected = normalized_words(reference)
    actual = normalized_words(hypothesis)
    if not expected:
        return 0.0 if not actual else 1.0
    previous = list(range(len(actual) + 1))
    for row_index, expected_word in enumerate(expected, start=1):
        current = [row_index]
        for column_index, actual_word in enumerate(actual, start=1):
            current.append(min(
                current[-1] + 1,
                previous[column_index] + 1,
                previous[column_index - 1] + (expected_word != actual_word),
            ))
        previous = current
    return round(min(1.0, previous[-1] / len(expected)), 4)
