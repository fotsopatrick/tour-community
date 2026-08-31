"""Test T11: Learning with 4 operations."""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tests.alicization_adapter import (
    AlicizationAdapter, apply_steps, apply_op, RunResult
)
from fixtures.procedure import op_k7, op_m2, op_q9, op_r4, op_t1, op_v6
import json

FIXTURE_4OPS = {
    "operations": {
        "op_k7": {"a": 3, "b": 7},
        "op_m2": {"a": 5, "b": 2},
        "op_q9": {"a": 2, "b": 11},
        "op_r4": {"a": 4, "b": 13},
        "op_t1": {"a": 7, "b": -3},
        "op_v6": {"a": 6, "b": 9},
    },
    "secret_procedure": ["op_q9", "op_r4", "op_k7", "op_m2"],
    "demo_input": 17,
}

DEMO_4OPS_INPUT = 17
# op_q9(17) = 45, op_r4(45) = 193, op_k7(193) = 586, op_m2(586) = 2932
DEMO_4OPS_OUTPUT = 2932


def demo_4ops():
    return {"input": DEMO_4OPS_INPUT, "output": DEMO_4OPS_OUTPUT}


@pytest.fixture()
def adapter():
    a = AlicizationAdapter()
    a.reset_state()
    return a


def test_11_four_ops_learning(adapter):
    """4 operations: q9 -> r4 -> k7 -> m2 transforms 17 into 2932."""
    r = adapter.teach(demo_4ops(), FIXTURE_4OPS)
    assert r.success, f"Teach failed: proposed={r.proposed_steps}"
    procedures = adapter.snapshot_state().get("procedures", [])
    assert procedures, "No learned procedure in DB."
    assert any(
        p.get("steps") == FIXTURE_4OPS["secret_procedure"]
        for p in procedures
    ), f"Wrong procedure. Expected {FIXTURE_4OPS['secret_procedure']}"
