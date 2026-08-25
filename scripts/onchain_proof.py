"""
onchain_proof.py

Runs the SAME vow logic as run_demo.sh, but for real, against the deployed
Orkos.sol contract on Base Sepolia -- not simulated locally. Produces real
transaction hashes you can link on Basescan, which is what actually proves
Base is load-bearing rather than an unused import.

Requires (already set from deployment):
    export DEPLOYER_PRIVATE_KEY=0x...
    export AGENT_ADDRESS=0x...
    export ORKOS_CONTRACT_ADDRESS=0x...   (printed by scripts/deploy.py)

Usage:
    python3 scripts/onchain_proof.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "agent"))

from onchain import submit_create_vow, submit_release, attempt_enforced_sell  # noqa: E402
from orkos_agent import VowRecord  # noqa: E402


def main():
    owner = os.environ.get("AGENT_ADDRESS")  # same wallet used for both roles
    if not owner:
        print("ERROR: AGENT_ADDRESS not set.")
        sys.exit(1)

    record = VowRecord(
        asset="ETH",
        protected_amount="10",
        thesis="Core ETH allocation held for L2 scaling thesis",
        invalidation_condition="a top-5 L2 by TVL migrates settlement off Ethereum mainnet",
        set_on="2026-08-25",
        prior_regret="Panic-sold 30 percent at -30 percent in June 2026, regretted it",
    )

    print("=== STEP 1: Creating vow ON-CHAIN (real transaction) ===")
    result = submit_create_vow(
        asset_address="0x0000000000000000000000000000000000dEaD",  # placeholder ERC-20 addr for demo
        protected_amount=10,
        floor_price_e8=0,
        thesis_hash=record.thesis_hash(),
    )
    print(result)
    vow_id = result["vow_id"]
    if vow_id is None:
        print("Could not read vow_id from event log -- check the tx on Basescan manually.")
        sys.exit(1)
    print(f"\nView this transaction: https://sepolia.basescan.org/tx/{result['tx_hash']}\n")

    print(f"=== STEP 2: Attempting a sell of the full protected amount (should REVERT) ===")
    check = attempt_enforced_sell(owner_address=owner, vow_id=vow_id, attempted_amount=10)
    print(check)

    print(f"\n=== STEP 3: Agent grants release (real transaction) ===")
    release = submit_release(owner_address=owner, vow_id=vow_id, reason_ref=record.thesis_hash())
    print(release)
    print(f"\nView this transaction: https://sepolia.basescan.org/tx/{release['tx_hash']}\n")

    print(f"=== STEP 4: Same sell attempt again -- should now SUCCEED (released) ===")
    check2 = attempt_enforced_sell(owner_address=owner, vow_id=vow_id, attempted_amount=10)
    print(check2)


if __name__ == "__main__":
    main()
