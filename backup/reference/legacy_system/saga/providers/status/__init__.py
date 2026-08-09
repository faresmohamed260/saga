from .shared import MODAL_POOL_PROVIDER

__all__ = [
    "MODAL_POOL_PROVIDER",
    "read_latest_inference_status_payload",
    "read_latest_provider_status_payload",
    "refresh_latest_provider_statuses",
]


def __getattr__(name: str):
    if name in {
        "read_latest_inference_status_payload",
        "read_latest_provider_status_payload",
        "refresh_latest_provider_statuses",
    }:
        from .service import (
            read_latest_inference_status_payload,
            read_latest_provider_status_payload,
            refresh_latest_provider_statuses,
        )

        mapping = {
            "read_latest_inference_status_payload": read_latest_inference_status_payload,
            "read_latest_provider_status_payload": read_latest_provider_status_payload,
            "refresh_latest_provider_statuses": refresh_latest_provider_statuses,
        }
        return mapping[name]
    raise AttributeError(name)
