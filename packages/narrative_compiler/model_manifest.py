"""Pinned V3.0 challenger metadata.

These are qualification candidates, not production-adoption declarations.
Keeping exact model revisions here prevents silent Hugging Face `main` drift.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CandidateModelPin:
    key: str
    model_id: str
    revision: str
    package: str
    package_version: str
    license_id: str
    role: str


GLINER25_BASE_V1 = CandidateModelPin(
    key="gliner2.5-base-v1",
    model_id="fastino/gliner2.5-base-v1",
    revision="ca906247640776a07753514055be9726f9080ead",
    package="gliner2",
    package_version="2.0.0",
    license_id="apache-2.0",
    role="semantic-lexer-challenger",
)

ETTIN_RERANKER_68M_V1 = CandidateModelPin(
    key="ettin-reranker-68m-v1",
    model_id="cross-encoder/ettin-reranker-68m-v1",
    revision="d166fa88ddde3c42bc3ee92f7df476d941c8204a",
    package="sentence-transformers",
    package_version="6.1.0",
    license_id="apache-2.0",
    role="identity-score-challenger",
)

V30_QUALIFICATION_CANDIDATES = (
    GLINER25_BASE_V1,
    ETTIN_RERANKER_68M_V1,
)
