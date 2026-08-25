<div align="center">

# Orkos

**The oath-keeper for onchain positions.**

An execution agent that blocks panic-sells — enforcing rules you set for yourself,
remembered via **Sibyl Memory**, enforced on **Base**.

[![Solidity](https://img.shields.io/badge/Solidity-0.8.24-black?style=flat&logo=solidity)](https://soliditylang.org/)
[![Python](https://img.shields.io/badge/Python-3.12-blue?style=flat&logo=python)](https://www.python.org/)
[![Base](https://img.shields.io/badge/Base-Sepolia-0052FF?style=flat&logo=coinbase)](https://base.org/)
[![Sibyl Memory](https://img.shields.io/badge/Sibyl_Memory-load--bearing-6E56CF?style=flat)](https://docs.sibyllabs.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

### Start here

| | |
|--|--|
| **Delete-memory test** | see [below](#the-delete-memory-test) — the whole rubric's 40 points, proven in one command |
| **On-chain proof** | see [below](#on-chain-proof-real-transactions) — real, verifiable transactions on Basescan, not simulated |
| **Deployed contract** | [`0xe24424586bCDc3Fdb5216721F9f9917344F9657e`](https://sepolia.basescan.org/address/0xe24424586bCDc3Fdb5216721F9f9917344F9657e) on Base Sepolia |
| **Run it yourself** | `bash scripts/run_demo.sh` — no setup beyond `pip install -r requirements.txt` |
| **Tests** | `python3 -m pytest tests/ -v` — 5 tests, including the delete-memory gate directly |
| **Demo video** | _(added once recorded — see [Status](#status))_ |

</div>

---

## What Orkos is

Named for Horkos, the Greek god who punished broken oaths. Orkos isn't a stop-loss —
a stop-loss fires mechanically on price. Orkos enforces a rule **you** set for
yourself, in a clear-headed moment, and refuses to let panic override it — even when
panic is the one holding the keys.

- A tool is an onchain contract (`Orkos.sol`) that can block or allow a sell.
- A "vow" is a rule: protect this amount, unless this specific condition is met.
- The agent reads the vow back from Sibyl Memory — in a completely fresh session —
  and decides whether a sell attempt honors it or breaks it.

No dashboard shows this. No price feed can derive it. The rule only exists because
something remembered it.

---

## The delete-memory test

> Delete the memory layer. If your project still does what it claims, it is a wrapper
> and does not qualify. If the core function breaks, memory is load-bearing.
> — [hack.sibyllabs.org](https://hack.sibyllabs.org)

**With memory:** the agent recalls a specific vow — why it was set, and what happened
the last time this person panic-sold — and blocks a sell that breaks it, or releases
it if the remembered condition is actually met.

**Without memory:** the agent has nothing to check the sell against. No on-chain
signal says "this wallet has a rule about this position" — that only exists in the
memory record. No memory, no block.

```bash
pip install -r requirements.txt
python3 -m pytest tests/test_agent.py::test_delete_memory_breaks -v
```

That single test is the eligibility gate, proven directly — not argued for.

For the full story (vow set → fresh session → block → legitimate release):

```bash
bash scripts/run_demo.sh
```

---

## On-chain proof (real transactions)

`scripts/run_demo.sh` above proves the memory logic, but it runs the decision layer
locally — it doesn't touch the blockchain. The four transactions below are the same
story, but for real, against the deployed contract on Base Sepolia. Every hash is
independently checkable on Basescan.

| Step | What happened | Proof |
|--|--|--|
| 1. Vow created | A real `createVow()` transaction, protecting 10 ETH, on-chain | [`0x9ec58dc1...4e7b4`](https://sepolia.basescan.org/tx/9ec58dc10863e75bfa0e5390a41d7e6d31c705d4095578a777983d4391d4e7b4) |
| 2. Blocked sell | Attempting to sell the protected amount reverts — `checkAndEnforce()` fires `VowViolated` on-chain, not in a simulation | error selector `0x901dffa2` returned directly from the contract call |
| 3. Vow released | The agent's `releaseVow()` call, a real transaction, unlocking the position | [`0xf410547a...1a04cf`](https://sepolia.basescan.org/tx/f410547aa566bff678acec60fecacc5becbc34769ee44396dd187c8db11a04cf) |
| 4. Sell now allowed | The exact same sell attempt that reverted in step 2 now returns `WOULD_SUCCEED` | reproduce with `python3 scripts/onchain_proof.py` |

Reproduce this yourself:

```bash
export DEPLOYER_PRIVATE_KEY=0x...
export AGENT_PRIVATE_KEY=0x...     # same key if using one wallet for both roles
export AGENT_ADDRESS=0x...
export ORKOS_CONTRACT_ADDRESS=0xe24424586bCDc3Fdb5216721F9f9917344F9657e
python3 scripts/onchain_proof.py
```

---

## Why Orkos

Every "AI trading assistant" gives you advice. None of them can actually stop you.

The moment that matters most — 40% down, panic in your chest, finger on the sell
button — is exactly the moment a person is least equipped to consult their own past
reasoning. Orkos isn't a smarter advisor. It's a **rule with teeth**: set by sober-you,
enforced onchain, and un-overridable by panicked-you talking your way past it.

- A vow lives in Sibyl Memory: what's protected, why, and what actually justifies
  letting it go.
- A sell attempt is checked against that memory — not against price, not against
  vibes.
- Only a genuinely matching condition unlocks release — this happens on Base, as a
  real transaction, not a suggestion in a chat window.

---

## How it works

1. **Set a vow** — in a sober session, you commit to a rule: protect this amount of
   this asset, unless \[specific condition] happens. Stored in Sibyl Memory, hashed
   and anchored on `Orkos.sol`.
2. **Attempt a sell** — days or weeks later, in a fresh session, a sell request comes
   in for the protected position.
3. **Agent recalls and decides** — `orkos_agent.py` reads the vow back from Sibyl
   Memory, checks the claimed reason against the remembered condition, and returns
   `BLOCK` or `RELEASE`.
4. **Contract enforces it** — a `BLOCK` means nothing is submitted, and
   `checkAndEnforce()` on Base would revert if anyone tried anyway. A `RELEASE`
   submits a real `releaseVow()` transaction, unlocking the position.

---

## Try it

```bash
# Set a vow (sober session)
python3 agent/orkos_agent.py set-vow eth-core \
  --asset ETH --amount 10 \
  --thesis "Core ETH allocation held for L2 scaling thesis" \
  --invalidation "a top-5 L2 by TVL migrates settlement off Ethereum mainnet" \
  --prior-regret "Panic-sold 30 percent at -30 percent in June 2026, regretted it"

# Fresh session — panic sell, unrelated reason → BLOCKED
python3 agent/orkos_agent.py attempt-sell eth-core --amount 10 \
  --reason "price is crashing I need to get out now"

# Fresh session — reason matches the remembered condition → RELEASED
python3 agent/orkos_agent.py attempt-sell eth-core --amount 10 \
  --reason "a top-5 L2 by TVL just migrated settlement off Ethereum mainnet"

# What the agent currently remembers
python3 agent/orkos_agent.py recall eth-core
```

---

## Architecture

```
┌───────────────────┐        ┌──────────────────────┐        ┌─────────────────┐
│  Sibyl Memory      │ read/  │  orkos_agent.py       │ tx     │  Orkos.sol       │
│  (file-based,      │ write  │  Decision layer:      │──────▶ │  On Base         │
│  SQLite-backed,    │◀──────▶│  BLOCK / RELEASE      │        │  Actually holds  │
│  no vector DB)     │        │  based on recalled    │        │  the position;   │
│                    │        │  vow vs. claimed      │        │  reverts if no   │
│  Stores: vow terms,│        │  reason for selling   │        │  release exists  │
│  thesis, prior     │        │                        │        │                  │
│  regret            │        │                        │        │                  │
└───────────────────┘        └──────────────────────┘        └─────────────────┘
```

```
orkos/
├── contracts/
│   ├── Orkos.sol              # on-chain enforcer — checkAndEnforce(), releaseVow()
│   ├── Orkos.abi.json          # generated by scripts/compile.js
│   └── Orkos.bytecode.txt
├── agent/
│   ├── orkos_agent.py          # Sibyl Memory decision layer (read/write vows, evaluate sells)
│   └── onchain.py              # bridges agent decisions to real Base transactions
├── scripts/
│   ├── compile.js              # compiles Orkos.sol, writes ABI + bytecode
│   ├── deploy.py               # deploys to Base Sepolia
│   ├── onchain_proof.py        # runs the real vow→block→release→allow cycle on-chain
│   └── run_demo.sh             # full end-to-end narrative, ready to screen-record
└── tests/
    └── test_agent.py           # 5 tests — recall, delete-memory gate, block/release/allow
```

- **`contracts/Orkos.sol`** — holds a vow's minimal enforceable terms (protected
  amount, a hash of the off-chain thesis). `checkAndEnforce()` reverts if a sell
  would touch the protected amount with no release granted. `releaseVow()` can only
  be called by the authorized agent address.
- **`agent/orkos_agent.py`** — reads/writes Sibyl Memory via the real
  `sibyl-memory-client` SDK. This is where recalled context (the vow's reasoning, the
  user's own prior-regret history) is checked against a claimed reason for selling.
- **`agent/onchain.py`** — a `RELEASE` decision submits `releaseVow()` on Base; a
  `BLOCK` decision means nothing is submitted at all.

### Why Base is load-bearing, not decorative

The vow's enforcement — the real ability to move or block funds — lives in the
deployed contract, not in the Python agent. Even if someone skipped the agent
entirely and called the contract directly, `checkAndEnforce()` still reverts unless
the agent already called `releaseVow()`. Take away Base and there's nothing stopping
the sell. Take away Sibyl Memory and the agent has no reason to ever grant a release.

---

## Running locally

```bash
git clone https://github.com/PhylippusRex/Orkos.git
cd Orkos
pip install -r requirements.txt
npm install

node scripts/compile.js          # compiles the contract
python3 -m pytest tests/ -v      # runs the test suite
bash scripts/run_demo.sh         # runs the full demo narrative
```

### Deploying to Base Sepolia (testnet only — no real funds)

```bash
export DEPLOYER_PRIVATE_KEY=0x...   # a Base Sepolia testnet wallet, funded via faucet
export AGENT_ADDRESS=0x...          # the address authorized to call releaseVow()
python3 scripts/deploy.py
```

---

## Status

v0.1 — built for the Sibyl Labs Hackathon (Sep 1–10, 2026).

- Sibyl Memory integration is real — set/recall tested across genuinely separate
  processes, not mocked. See `tests/test_agent.py::test_fresh_session_recall`.
- `Orkos.sol` is deployed and live on Base Sepolia:
  [`0xe24424586bCDc3Fdb5216721F9f9917344F9657e`](https://sepolia.basescan.org/address/0xe24424586bCDc3Fdb5216721F9f9917344F9657e).
- The full vow → block → release → allow cycle has been run against the live
  contract with real transactions — see [On-chain proof](#on-chain-proof-real-transactions) above.
- The invalidation-condition check is a keyword match against the remembered
  condition, not a live price/data feed — a scope call for a 10-day build, not a
  gap we're hiding. A real oracle (e.g. Chainlink on Base) is the natural next step.
- Demo video: added once recorded.

---

## License

MIT — see [LICENSE](./LICENSE).

---

<div align="center">

**Built by [Philippus](https://github.com/PhylippusRex)** for the Sibyl Labs Hackathon

</div>
