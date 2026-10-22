"""LLM/NLI-assisted claim comparison interface (Baseline C). Intentionally has no implementation.

No model or credentials are bundled. Calling it raises ModelUnavailable; the pipeline must then fall back
to deterministic checks and say so, never inventing a verdict.
"""
from ..orchestration.pipeline import ModelUnavailable


class SemanticVerifier:
    version = "unavailable"

    def compare(self, claim_a, claim_b):
        raise ModelUnavailable("No semantic verifier configured; LLM-assisted comparison was not run.")
