"""
orkos_agent.py

The agent layer of Orkos. This is the piece that makes Sibyl Memory
load-bearing rather than decorative: it is the ONLY thing that can grant a
release on a blocked vow, and it can only do that by reading a remembered
vow record and reasoning about whether the recalled invalidation condition
is genuinely met.

Delete this agent's access to Sibyl Memory and it has no vow to check
against at all -- it cannot distinguish a legitimate exit from a panic
sell, because the entire distinction lives in the remembered record, not
in anything derivable from live market data alone.

Real SDK in use: sibyl_memory_client.MemoryClient / Storage (file-based,
SQLite-backed, no vector DB -- matches Sibyl Labs' documented architecture).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sibyl_memory_client import MemoryClient, Storage, NotFoundError

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "orkos_memory.db"
VOW_CATEGORY = "vow"
INCIDENT_CATEGORY = "vow_incident"  # log of every check, for the demo's audit trail


def _client(db_path: Path = DEFAULT_DB_PATH) -> MemoryClient:
    """
    Construct a brand-new MemoryClient against the on-disk store.

    Calling this fresh (new Storage object, new MemoryClient object) in a
    new process is what makes the "fresh session" claim genuine rather than
    theatrical -- nothing is cached in this process's memory from a prior
    run; everything comes back from disk.
    """
    storage = Storage(str(db_path))
    return MemoryClient(storage)


@dataclass
class VowRecord:
    asset: str
    protected_amount: str
    thesis: str
    invalidation_condition: str
    set_on: str
    prior_regret: str | None = None

    def thesis_hash(self) -> str:
        """Hash used to anchor the on-chain Orkos.sol vow to this off-chain record."""
        payload = json.dumps(asdict(self), sort_keys=True).encode()
        return "0x" + hashlib.sha256(payload).hexdigest()


def set_vow(name: str, record: VowRecord, db_path: Path = DEFAULT_DB_PATH) -> dict[str, Any]:
    """
    Called in a SOBER session, before any panic scenario exists. This is
    the moment the user commits to a rule about their own future behavior.
    """
    client = _client(db_path)
    result = client.set_entity(VOW_CATEGORY, name, asdict(record))
    print(f"[orkos] Vow '{name}' persisted to Sibyl Memory.")
    print(f"[orkos] thesis_hash for on-chain anchoring: {record.thesis_hash()}")
    return result


def recall_vow(name: str, db_path: Path = DEFAULT_DB_PATH) -> VowRecord | None:
    """
    Called in a genuinely fresh session -- this function makes no assumption
    that anything about the vow is already known. If Sibyl Memory has never
    heard of this vow (or memory access is removed entirely), this returns
    None, and the caller has NOTHING to check the sell attempt against.
    """
    client = _client(db_path)
    try:
        entity = client.get_entity(VOW_CATEGORY, name)
    except NotFoundError:
        return None
    body = entity["body"]
    return VowRecord(**body)


def log_incident(name: str, action: str, detail: str, db_path: Path = DEFAULT_DB_PATH) -> None:
    """Append-only incident log -- this is what the demo shows on screen as proof."""
    client = _client(db_path)
    ts = datetime.now(timezone.utc).isoformat()
    client.set_entity(INCIDENT_CATEGORY, f"{name}-{ts}", {
        "vow_name": name,
        "action": action,
        "detail": detail,
        "timestamp": ts,
    })


def evaluate_sell_attempt(
    vow_name: str,
    attempted_amount: float,
    claimed_reason: str,
    db_path: Path = DEFAULT_DB_PATH,
) -> dict[str, Any]:
    """
    The core decision function. This is what runs when "panicked future you"
    (or a relayer acting on their behalf) tries to execute a sell.

    Returns a decision dict: {"action": "BLOCK" | "RELEASE", "reasoning": str, ...}

    NOTE on scope: the invalidation-condition check here is intentionally a
    simple keyword/semantic match against the remembered condition, not a
    live market-data oracle. Wiring a real price/TVL oracle is a natural
    next step post-hackathon, flagged in the README -- for the demo, what
    matters is proving the DECISION changes because of RECALLED CONTEXT,
    not building a production-grade market data pipeline in 10 days.
    """
    vow = recall_vow(vow_name, db_path)

    if vow is None:
        # No memory access, or nothing was ever remembered. This branch is
        # the "delete memory and the app breaks" case -- with nothing to
        # check against, there is no principled basis to block anything.
        decision = {
            "action": "NO_VOW_FOUND",
            "reasoning": (
                "No vow record recalled for this position. Without a "
                "remembered commitment, this agent has no basis to "
                "distinguish a panic sell from a legitimate exit -- "
                "the sell would proceed unchecked."
            ),
        }
        log_incident(vow_name, decision["action"], decision["reasoning"], db_path)
        return decision

    protected = float(vow.protected_amount)
    would_touch_protected_amount = attempted_amount >= protected

    if not would_touch_protected_amount:
        decision = {
            "action": "ALLOW",
            "reasoning": f"Attempted sell ({attempted_amount}) is below the protected "
                         f"amount ({protected}) set in the vow. No conflict.",
        }
        log_incident(vow_name, decision["action"], decision["reasoning"], db_path)
        return decision

    # Attempted sell touches the protected core position. Check the claimed
    # reason against the REMEMBERED invalidation condition -- this is the
    # single line where recalled, personal context changes the outcome.
    condition_met = _condition_genuinely_met(claimed_reason, vow.invalidation_condition)

    if condition_met:
        decision = {
            "action": "RELEASE",
            "reasoning": f"Claimed reason matches the remembered invalidation "
                         f"condition ('{vow.invalidation_condition}'). Releasing vow.",
            "thesis_hash": vow.thesis_hash(),
        }
    else:
        regret_note = f" Recorded prior regret: \"{vow.prior_regret}\"." if vow.prior_regret else ""
        decision = {
            "action": "BLOCK",
            "reasoning": (
                f"Sell of {attempted_amount} would touch the protected core position "
                f"({protected}). Remembered vow requires: '{vow.invalidation_condition}'. "
                f"Claimed reason ('{claimed_reason}') does not match this condition."
                f"{regret_note}"
            ),
        }

    log_incident(vow_name, decision["action"], decision["reasoning"], db_path)
    return decision


def _condition_genuinely_met(claimed_reason: str, invalidation_condition: str) -> bool:
    """
    Deliberately conservative: only releases if the claimed reason strongly
    overlaps with the specific, remembered invalidation condition. A bare
    "price dropped" or "I'm scared" claim will NOT match a condition like
    "a top-5 L2 by TVL migrates settlement off Ethereum mainnet" -- which is
    exactly the point. Panic doesn't get to rewrite the remembered rule.
    """
    claimed = claimed_reason.lower()
    condition = invalidation_condition.lower()
    condition_keywords = {w for w in condition.split() if len(w) > 4}
    hits = sum(1 for w in condition_keywords if w in claimed)
    return len(condition_keywords) > 0 and hits / len(condition_keywords) >= 0.5


def _cli() -> None:
    parser = argparse.ArgumentParser(description="Orkos agent -- Sibyl Memory-backed vow enforcement")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_set = sub.add_parser("set-vow", help="Create a vow in a sober session")
    p_set.add_argument("name")
    p_set.add_argument("--asset", required=True)
    p_set.add_argument("--amount", required=True)
    p_set.add_argument("--thesis", required=True)
    p_set.add_argument("--invalidation", required=True)
    p_set.add_argument("--prior-regret", default=None)

    p_check = sub.add_parser("attempt-sell", help="Simulate a fresh-session sell attempt")
    p_check.add_argument("name")
    p_check.add_argument("--amount", required=True, type=float)
    p_check.add_argument("--reason", required=True)

    p_recall = sub.add_parser("recall", help="Show what the agent currently remembers")
    p_recall.add_argument("name")

    args = parser.parse_args()

    if args.cmd == "set-vow":
        record = VowRecord(
            asset=args.asset,
            protected_amount=args.amount,
            thesis=args.thesis,
            invalidation_condition=args.invalidation,
            set_on=datetime.now(timezone.utc).date().isoformat(),
            prior_regret=args.prior_regret,
        )
        set_vow(args.name, record)

    elif args.cmd == "attempt-sell":
        decision = evaluate_sell_attempt(args.name, args.amount, args.reason)
        print(json.dumps(decision, indent=2))
        if decision["action"] == "BLOCK":
            sys.exit(1)  # non-zero exit so this is scriptable/demoable as a hard stop

    elif args.cmd == "recall":
        vow = recall_vow(args.name)
        if vow is None:
            print(f"[orkos] Nothing remembered for '{args.name}'.")
        else:
            print(json.dumps(asdict(vow), indent=2))


if __name__ == "__main__":
    _cli()
