import json
from pathlib import Path
import pytest

from alicization_adapter import AlicizationAdapter
from oracle import apply_procedure

FIXTURE = json.loads((Path(__file__).parents[1] / "fixtures" / "procedure.json").read_text())

def oracle_value(key):
    return apply_procedure(
        FIXTURE[key],
        FIXTURE["secret_procedure"],
        FIXTURE["operations"],
    )

def demo():
    return {
        "input": FIXTURE["demo_input"],
        "output": oracle_value("demo_input"),
    }

@pytest.fixture()
def adapter():
    a = AlicizationAdapter()
    a.reset_state()
    return a

def test_01_baseline_absence(adapter):
    r = adapter.baseline(FIXTURE["demo_input"], FIXTURE)
    assert not r.success, "Baseline already performs the unseen procedure."

def test_02_external_experience_created(adapter):
    adapter.teach(demo(), FIXTURE)
    state = adapter.snapshot_state()
    assert state.get("experiences"), "No persisted experience was created."

def test_03_external_procedure_created(adapter):
    adapter.teach(demo(), FIXTURE)
    procedures = adapter.snapshot_state().get("procedures", [])
    assert procedures, "No learned external procedure exists."
    assert any(p.get("steps") == FIXTURE["secret_procedure"] for p in procedures)

def test_04_unverified_procedure_not_active(adapter):
    adapter.teach(demo(), FIXTURE)
    procedures = adapter.snapshot_state().get("procedures", [])
    assert all(p.get("status") != "ACTIVE" for p in procedures)

def test_05_reuse_after_demo_removed(adapter):
    adapter.teach(demo(), FIXTURE)
    adapter.remove_demo_context()
    r = adapter.reuse(FIXTURE["reuse_input"], FIXTURE)
    assert r.success
    assert r.output == oracle_value("reuse_input")

def test_06_generalization(adapter):
    adapter.teach(demo(), FIXTURE)
    adapter.remove_demo_context()
    r = adapter.reuse(FIXTURE["generalization_input"], FIXTURE)
    assert r.success
    assert r.output == oracle_value("generalization_input")

def test_07_retention_after_restart(adapter):
    adapter.teach(demo(), FIXTURE)
    adapter.remove_demo_context()
    adapter.restart()
    r = adapter.reuse(FIXTURE["retention_input"], FIXTURE)
    assert r.success
    assert r.output == oracle_value("retention_input")

def test_08_memory_dependency(adapter):
    adapter.teach(demo(), FIXTURE)
    adapter.remove_demo_context()
    good = adapter.reuse(211, FIXTURE)
    assert good.success
    state = adapter.state()
    assert state.get("procedures"), "No learned state exists for dependency control."
    assert hasattr(adapter, "hide_learned_state"),         "Adapter must implement hide_learned_state for this proof control."
    adapter.hide_learned_state()
    bad = adapter.reuse(211, FIXTURE)
    assert not bad.success, "Behavior still succeeds after learned external state is hidden."

def test_09_raw_evidence(adapter):
    adapter.teach(demo(), FIXTURE)
    assert isinstance(adapter.raw_events(), list)
    assert isinstance(adapter.raw_model_io(), list)

def test_10_learning_proven(adapter):
    adapter.reset_state()
    baseline = adapter.baseline(FIXTURE["demo_input"], FIXTURE)
    assert not baseline.success

    adapter.teach(demo(), FIXTURE)
    procedures = adapter.snapshot_state().get("procedures", [])
    assert procedures

    adapter.remove_demo_context()
    reuse = adapter.reuse(FIXTURE["reuse_input"], FIXTURE)
    assert reuse.success
    assert reuse.output == oracle_value("reuse_input")

    general = adapter.reuse(FIXTURE["generalization_input"], FIXTURE)
    assert general.success
    assert general.output == oracle_value("generalization_input")

    adapter.restart()
    retained = adapter.reuse(FIXTURE["retention_input"], FIXTURE)
    assert retained.success
    assert retained.output == oracle_value("retention_input")
