from saga.persistence.provider_config_store import ProviderConfigStore
from saga.providers.reasoning_runtime_adapter import build_reasoning_runtime_config
from saga.storage.persistence import SagaRelationalStore


def test_provider_config_store_is_relational_store_backed(tmp_path):
    store = SagaRelationalStore(tmp_path / "saga.sqlite")
    provider_store = ProviderConfigStore(store)

    provider_store.upsert_provider_config("general_compute", {"provider_name": "general_compute", "accounts": [{"label": "primary", "api_key": "gc-test"}]})

    payload = provider_store.get_provider_config("general_compute")
    assert payload is not None
    assert payload["accounts"][0]["api_key"] == "gc-test"


def test_reasoning_runtime_config_reads_general_compute_state_from_database(tmp_path):
    store = SagaRelationalStore(tmp_path / "saga.sqlite")
    ProviderConfigStore(store).upsert_provider_config(
        "general_compute",
        {
            "provider_name": "general_compute",
            "active_index": 1,
            "last_request_index": 0,
            "accounts": [
                {
                    "label": "gc-a",
                    "api_key": "gc-key-a",
                    "limits": {"requests_per_minute": 3},
                    "usage": {"minute_requests": 1},
                    "metadata": {"region": "us"},
                },
                {"label": "gc-b", "api_key": "gc-key-b"},
            ],
        },
    )

    config = build_reasoning_runtime_config(store=store)

    assert len(config.general_compute_accounts) == 2
    assert config.general_compute_accounts[0].limits["requests_per_minute"] == 3
    assert config.general_compute_accounts[0].usage["minute_requests"] == 1
    assert config.general_compute_accounts[0].metadata["region"] == "us"
    assert config.general_compute_active_index == 1
    assert config.general_compute_last_request_index == 0


def test_reasoning_runtime_config_reads_ollama_accounts_from_database(tmp_path):
    store = SagaRelationalStore(tmp_path / "saga.sqlite")
    ProviderConfigStore(store).upsert_provider_config(
        "ollama",
        {
            "provider_name": "ollama",
            "active_index": 0,
            "accounts": [
                {
                    "label": "ollama-a",
                    "api_key": "ollama-key",
                    "email": "user@example.com",
                    "password": "secret",
                    "metadata": {"transport": "cloud"},
                }
            ],
        },
    )

    config = build_reasoning_runtime_config(store=store)

    assert len(config.ollama_accounts) == 1
    assert config.ollama_accounts[0].api_key == "ollama-key"
    assert config.ollama_accounts[0].email == "user@example.com"
    assert config.ollama_accounts[0].password == "secret"
    assert config.ollama_accounts[0].metadata["transport"] == "cloud"
