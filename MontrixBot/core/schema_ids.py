from __future__ import annotations


class SchemaIds:
    """
    Canonical schema IDs for runtime artifacts (STEP 1.9.B).
    """
    SCHEMA_MANIFEST = "runtime.schema_manifest"
    SIGNALS_RECORD = "runtime.signals_record"
    CLOCK_SNAPSHOT = "runtime.clock_snapshot"
    REPLAY_LAST = "runtime.replay_last"
    INCIDENTS_LAST = "runtime.incidents_last"
    READINESS_LAST = "runtime.readiness_last"
    POLICY_TRACE_EVENT = "runtime.policy_trace_event"
    RUNTIME_GUARD_RAILS_STATE = ("runtime.guard_rails_state", 1)

class SchemaVersions:
    """
    Canonical schema versions for runtime artifacts (STEP 1.9.B).
    """
    V1 = 1
