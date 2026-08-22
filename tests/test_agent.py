"""
Test suite for orkos_agent.py.

Run with: pytest tests/test_agent.py -v

These tests are the actual evidence backing every claim in the pitch:
1. test_fresh_session_recall     -> proves genuine cross-session persistence
2. test_delete_memory_breaks     -> proves the eligibility gate directly
3. test_block_on_unmatched_reason -> proves panic can't talk its way past a vow
4. test_release_on_matched_condition -> proves legitimate exits still work
5. test_amount_below_threshold_allowed -> proves it's not just a blanket freeze
"""

import sys
from pathlib import Path
import tempfile

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "agent"))

from orkos_agent import VowRecord, set_vow, recall_vow, evaluate_sell_attempt  # noqa: E402


@pytest.fixture
def db_path():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d) / "test_orkos.db"


def _sample_vow():
    return VowRecord(
        asset="ETH",
        protected_amount="10",
        thesis="Core ETH allocation held for L2 scaling thesis",
        invalidation_condition="a top-5 L2 by TVL migrates settlement off Ethereum mainnet",
        set_on="2026-08-18",
        prior_regret="Panic-sold 30 percent at -30 percent in June 2026, regretted it",
    )


def test_fresh_session_recall(db_path):
    """A vow set in one MemoryClient instance is recallable from a brand new one."""
    set_vow("eth-core", _sample_vow(), db_path=db_path)

    # New instance -- simulates a genuinely separate process/session.
    recalled = recall_vow("eth-core", db_path=db_path)

    assert recalled is not None
    assert recalled.asset == "ETH"
    assert recalled.invalidation_condition == _sample_vow().invalidation_condition


def test_delete_memory_breaks(db_path):
    """
    The eligibility gate, proven directly: with NO vow ever recorded (i.e.
    memory deleted/absent), the agent has no basis to block anything.
    """
    decision = evaluate_sell_attempt(
        "never-recorded-vow", attempted_amount=10, claimed_reason="panic", db_path=db_path
    )
    assert decision["action"] == "NO_VOW_FOUND"


def test_block_on_unmatched_reason(db_path):
    """Panic-flavored reasoning that doesn't match the remembered condition gets blocked."""
    set_vow("eth-core", _sample_vow(), db_path=db_path)
    decision = evaluate_sell_attempt(
        "eth-core", attempted_amount=10, claimed_reason="price is crashing, I need out now", db_path=db_path
    )
    assert decision["action"] == "BLOCK"
    assert "prior regret" in decision["reasoning"].lower()


def test_release_on_matched_condition(db_path):
    """A claimed reason that genuinely matches the remembered invalidation condition releases."""
    set_vow("eth-core", _sample_vow(), db_path=db_path)
    decision = evaluate_sell_attempt(
        "eth-core",
        attempted_amount=10,
        claimed_reason="a top-5 L2 by TVL just migrated settlement off Ethereum mainnet",
        db_path=db_path,
    )
    assert decision["action"] == "RELEASE"
    assert "thesis_hash" in decision


def test_amount_below_threshold_allowed(db_path):
    """Selling less than the protected amount never triggers the vow at all."""
    set_vow("eth-core", _sample_vow(), db_path=db_path)
    decision = evaluate_sell_attempt(
        "eth-core", attempted_amount=2, claimed_reason="rebalancing a small amount", db_path=db_path
    )
    assert decision["action"] == "ALLOW"
