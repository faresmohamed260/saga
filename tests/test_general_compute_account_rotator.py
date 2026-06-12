import json
from datetime import datetime, timezone
from pathlib import Path

from infrastructure.general_compute_account_rotator import GeneralComputeAccountRotator


def test_acquire_api_key_for_request_rotates_to_next_available_key(tmp_path):
    now = datetime.now(timezone.utc)
    minute_key = now.strftime("%Y-%m-%dT%H:%M")
    day_key = now.strftime("%Y-%m-%d")
    config_path = tmp_path / "accounts.local.json"
    config_path.write_text(
        json.dumps(
            {
                "active_index": 0,
                "last_request_index": -1,
                "accounts": [
                    {
                        "label": "gc-a",
                        "api_key": "key-a",
                        "limits": {
                            "requests_per_minute": 1,
                            "input_tokens_per_minute": 1000,
                            "output_tokens_per_minute": 1000,
                            "requests_per_day": 1000,
                            "tokens_per_day": 500000,
                        },
                        "usage": {
                            "minute_window_started_at": minute_key,
                            "day_window_started_on": day_key,
                            "minute_requests": 1,
                            "minute_input_tokens": 0,
                            "minute_output_tokens": 0,
                            "minute_tokens": 0,
                            "day_requests": 1,
                            "day_tokens": 0,
                        },
                    },
                    {
                        "label": "gc-b",
                        "api_key": "key-b",
                        "limits": {
                            "requests_per_minute": 1,
                            "input_tokens_per_minute": 1000,
                            "output_tokens_per_minute": 1000,
                            "requests_per_day": 1000,
                            "tokens_per_day": 500000,
                        },
                        "usage": {
                            "minute_window_started_at": minute_key,
                            "day_window_started_on": day_key,
                            "minute_requests": 0,
                            "minute_input_tokens": 0,
                            "minute_output_tokens": 0,
                            "minute_tokens": 0,
                            "day_requests": 0,
                            "day_tokens": 0,
                        },
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    rotator = GeneralComputeAccountRotator(config_path)
    selected = rotator.acquire_api_key_for_request(estimated_tokens=500, wait=False)
    assert selected == "key-b"


def test_acquire_api_key_for_request_returns_empty_when_all_keys_exhausted_and_wait_disabled(tmp_path):
    now = datetime.now(timezone.utc)
    minute_key = now.strftime("%Y-%m-%dT%H:%M")
    day_key = now.strftime("%Y-%m-%d")
    config_path = tmp_path / "accounts.local.json"
    config_path.write_text(
        json.dumps(
            {
                "active_index": 0,
                "last_request_index": -1,
                "accounts": [
                    {
                        "label": "gc-a",
                        "api_key": "key-a",
                        "limits": {
                            "requests_per_minute": 1,
                            "input_tokens_per_minute": 1000,
                            "output_tokens_per_minute": 1000,
                            "requests_per_day": 1000,
                            "tokens_per_day": 500000,
                        },
                        "usage": {
                            "minute_window_started_at": minute_key,
                            "day_window_started_on": day_key,
                            "minute_requests": 1,
                            "minute_input_tokens": 1000,
                            "minute_output_tokens": 1000,
                            "minute_tokens": 2000,
                            "day_requests": 1,
                            "day_tokens": 10000,
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    rotator = GeneralComputeAccountRotator(config_path)
    assert rotator.acquire_api_key_for_request(estimated_tokens=1, wait=False) == ""


def test_acquire_api_key_for_request_respects_output_token_limit(tmp_path):
    now = datetime.now(timezone.utc)
    minute_key = now.strftime("%Y-%m-%dT%H:%M")
    day_key = now.strftime("%Y-%m-%d")
    config_path = tmp_path / "accounts.local.json"
    config_path.write_text(
        json.dumps(
            {
                "active_index": 0,
                "last_request_index": -1,
                "accounts": [
                    {
                        "label": "gc-a",
                        "api_key": "key-a",
                        "limits": {
                            "requests_per_minute": 60,
                            "input_tokens_per_minute": 100000,
                            "output_tokens_per_minute": 1000,
                            "requests_per_day": 1000,
                            "tokens_per_day": 500000,
                        },
                        "usage": {
                            "minute_window_started_at": minute_key,
                            "day_window_started_on": day_key,
                            "minute_requests": 0,
                            "minute_input_tokens": 0,
                            "minute_output_tokens": 900,
                            "minute_tokens": 900,
                            "day_requests": 0,
                            "day_tokens": 900,
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    rotator = GeneralComputeAccountRotator(config_path)
    assert rotator.acquire_api_key_for_request(
        estimated_input_tokens=100,
        estimated_output_tokens=200,
        wait=False,
    ) == ""
