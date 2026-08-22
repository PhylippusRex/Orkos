#!/usr/bin/env bash
# run_demo.sh
#
# Runs the full Orkos narrative in order, meant to be screen-recorded
# directly for the hackathon submission (2-5 min demo requirement).
# Each section pauses briefly so the terminal output is readable on camera.
set -e
cd "$(dirname "$0")/.."

# Normal recording speed uses real pauses (arg in seconds, default 2).
# For a quick dry-run while testing: DEMO_FAST=1 bash scripts/run_demo.sh
pause() {
  if [ -n "$DEMO_FAST" ]; then
    sleep 0.1
  else
    sleep "${1:-2}"
  fi
}

clear
echo "================================================================"
echo " ORKOS -- an agent that remembers your sober rules so panic can't"
echo "         override them."
echo "================================================================"
pause 3

rm -f orkos_memory.db*

echo ""
echo ">>> SESSION A -- sober session, today. Setting a vow on core ETH."
echo ""
pause 1
python3 agent/orkos_agent.py set-vow eth-core \
  --asset ETH \
  --amount 10 \
  --thesis "Core ETH allocation held for L2 scaling thesis" \
  --invalidation "a top-5 L2 by TVL migrates settlement off Ethereum mainnet" \
  --prior-regret "Panic-sold 30 percent at -30 percent in the June 2026 drawdown, thesis was still intact, regretted it within a week"
pause 3

echo ""
echo "================================================================"
echo " Terminal closed. New process starting below."
echo " This is a genuinely fresh session -- nothing is cached."
echo "================================================================"
pause 2

echo ""
echo ">>> WITHOUT MEMORY -- same sell attempt, against a wallet that has"
echo "    never recorded a vow (the delete-memory eligibility test):"
echo ""
pause 1
python3 -c "
import sys
sys.path.insert(0, 'agent')
from orkos_agent import evaluate_sell_attempt
from pathlib import Path
import json
decision = evaluate_sell_attempt('eth-core', 10, 'price is crashing I need to get out now', db_path=Path('no_memory_demo.db'))
print(json.dumps(decision, indent=2))
"
rm -f no_memory_demo.db*
pause 3

echo ""
echo ">>> SESSION B -- fresh session, weeks later. Market just dropped 40%."
echo "    Attempting to sell the full 10 ETH core position."
echo ""
pause 1
set +e
python3 agent/orkos_agent.py attempt-sell eth-core --amount 10 --reason "price is crashing I need to get out now"
set -e
pause 3

echo ""
echo ">>> Same session, but the L2-migration condition genuinely occurs."
echo "    Legitimate exit -- the vow releases."
echo ""
pause 1
python3 agent/orkos_agent.py attempt-sell eth-core --amount 10 --reason "a top-5 L2 by TVL just migrated settlement off Ethereum mainnet"
pause 3

echo ""
echo "================================================================"
echo " That RELEASE decision is what submits releaseVow() on Base --"
echo " see agent/onchain.py. The BLOCK above means checkAndEnforce()"
echo " would revert on-chain if anyone tried anyway."
echo "================================================================"

rm -f orkos_memory.db*
