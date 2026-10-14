"""Workflow spans whose W3C trace id doubles as the agent `trace_id` (App Insights `operation_Id`)."""

from __future__ import annotations

import logging
import secrets
from collections.abc import Iterator
from contextlib import contextmanager

from opentelemetry import trace

logger = logging.getLogger(__name__)

WORKFLOW_SPAN = "tactistream.explain_moment"


@contextmanager
def workflow_span(
    match_id: str, moment_id: str, *, config: str = "live", tracer: trace.Tracer | None = None
) -> Iterator[str]:
    """Open `tactistream.explain_moment` and yield its 32-hex trace id."""
    tracer = tracer or trace.get_tracer("tactistream")
    attributes = {"match_id": match_id, "moment_id": moment_id, "config": config}
    with tracer.start_as_current_span(WORKFLOW_SPAN, attributes=attributes) as span:
        context = span.get_span_context()
        if context.is_valid:
            yield format(context.trace_id, "032x")
        else:
            logger.warning("no SDK tracer provider; %s/%s gets an uncorrelated trace id", match_id, moment_id)
            yield secrets.token_hex(16)


def current_trace_id() -> str | None:
    context = trace.get_current_span().get_span_context()
    return format(context.trace_id, "032x") if context.is_valid else None
