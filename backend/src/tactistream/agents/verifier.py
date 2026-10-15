"""Verifier: deterministic pre-checks plus model judgement; the stricter verdict wins."""

from __future__ import annotations

from collections.abc import Mapping

from tactistream.contracts import Verdict
from tactistream.contracts.claim import Decision, ReasonCode

_SEVERITY: Mapping[Decision, int] = {"approve": 0, "revise": 1, "reject": 2}


def combine_verdicts(pre: Verdict, model: Verdict | None) -> Verdict:
    """Stricter decision; reason codes unioned in order (`ok` only if nothing else); model note preferred."""
    if model is None:
        return pre
    if model.claim_id != pre.claim_id:
        raise ValueError(f"cannot combine verdicts for {pre.claim_id} and {model.claim_id}")
    decision = max(pre.decision, model.decision, key=_SEVERITY.__getitem__)
    codes: list[ReasonCode] = []
    for code in (*pre.reason_codes, *model.reason_codes):
        if code != "ok" and code not in codes:
            codes.append(code)
    return Verdict(
        claim_id=pre.claim_id,
        decision=decision,
        reason_codes=codes or ["ok"],
        note=model.note or pre.note,
    )
