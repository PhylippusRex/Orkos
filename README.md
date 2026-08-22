# Orkos

**An onchain execution agent that enforces self-authored commitments against panic-selling.**

Built for the [Sibyl Labs Hackathon](https://hack.sibyllabs.org) (Sep 1–10, 2026).

Named for Horkos, the Greek god who punished broken oaths. Orkos isn't a stop-loss —
stop-losses execute mechanically on price. Orkos enforces a *rule you set for yourself
when you were thinking clearly*, and refuses to let panic override it, even when panic
is holding the keyboard.

---

## The delete-memory test

> Delete the memory layer. If your project still does what it claims, it is a wrapper
> and does not qualify. If the core function breaks, memory is load-bearing.
> — [hack.sibyllabs.org](https://hack.sibyllabs.org)

Orkos passes this directly and demonstrably:

- **With memory:** the agent recalls a specific, self-authored vow — including *why*
  it was set and what happened the last time this exact person panic-sold — and blocks
  a sell that violates it, or releases it if the remembered invalidation condition is
  genuinely met.
- **Without memory:** the agent has *nothing to check the sell against*. There is no
  public, on-chain signal that distinguishes "this person set a rule about this
  position" from any other wallet. The block/release decision cannot exist without the
  recalled record — see `tests/test_agent.py::test_delete_memory_breaks`.

Run it yourself:

```bash
pip install -r requirements.txt
bash scripts/run_demo.sh
```

This runs the full narrative: a sober session sets a vow, a fresh session attempts a
panic sell and gets blocked (with the exact remembered reasoning cited), the same
sell attempt against a wallet with no memory at all proceeds unchecked, and a
legitimate exit (the remembered invalidation condition genuinely occurring) releases
the vow.

---

## Architecture

```
┌─────────────────────┐        ┌──────────────────────┐        ┌─────────────────┐
│   Sibyl Memory       │ read/  │   orkos_agent.py      │ tx     │   Orkos.sol      │
│   (file-based,       │ write  │   Decision layer:     │──────▶ │   On Base        │
│   SQLite-backed,     │◀──────▶│   BLOCK / RELEASE      │        │   Actually holds │
│   no vector DB)       │        │   based on recalled    │        │   the position;  │
│                       │        │   vow vs. claimed       │        │   reverts if no  │
│  Stores: vow terms,   │        │   reason for selling    │        │   release exists │
│  thesis, prior regret │        │                         │        │                  │
└─────────────────────┘        └──────────────────────┘        └─────────────────┘
```

- **`contracts/Orkos.sol`** — the on-chain enforcer. Holds a vow's *minimal enforceable
  terms* (protected amount, a hash of the off-chain thesis). `checkAndEnforce()` reverts
  if a sell would touch the protected amount and no release has been granted.
  `releaseVow()` can only be called by the authorized agent address.
- **`agent/orkos_agent.py`** — the decision layer. Reads/writes Sibyl Memory via the
  real `sibyl-memory-client` SDK. This is where recalled context (the vow's rationale,
  the user's own prior-regret history) is checked against a claimed reason for selling.
- **`agent/onchain.py`** — bridges an agent decision to a real Base transaction. A
  `RELEASE` decision submits `releaseVow()` on-chain; a `BLOCK` decision means nothing
  is submitted, and `checkAndEnforce()` would revert if anyone tried anyway.

## Why Base is load-bearing, not decorative

The vow's *enforcement* — the actual ability to move or not move funds — lives in the
deployed contract, not in the Python agent. Even if someone bypassed the agent
entirely and called the contract directly, `checkAndEnforce()` still reverts without a
prior `releaseVow()` call from the authorized agent. The agent's Sibyl-Memory-informed
decision is what produces (or withholds) that on-chain release. Pull Base out and
there's no real barrier to the sell going through — pull Sibyl Memory out and the
agent has no basis to ever grant a release in the first place.

## Scope note (10-day hackathon build)

The invalidation-condition check (`_condition_genuinely_met` in `orkos_agent.py`) is a
deliberately conservative keyword-overlap match against the remembered condition, not
a live market-data/oracle integration. This was a scope decision: the rubric scores
whether *recalled memory changes a real decision*, not whether we built a production
oracle pipeline in 10 days. Wiring a real price/TVL oracle (e.g. Chainlink on Base) is
the natural next step post-hackathon and is noted as such rather than faked.

## Setup

```bash
git clone <this-repo>
cd orkos
pip install -r requirements.txt
npm install

# Compile the contract (writes contracts/Orkos.abi.json + Orkos.bytecode.txt)
node scripts/compile.js

# Run tests
python3 -m pytest tests/ -v

# Run the full demo narrative
bash scripts/run_demo.sh
```

### Deploying to Base Sepolia (optional — testnet only, no real funds)

```bash
export DEPLOYER_PRIVATE_KEY=0x...   # a Base Sepolia testnet wallet, funded via faucet
export AGENT_ADDRESS=0x...          # the address authorized to call releaseVow()
python3 scripts/deploy.py
```

## Repo structure

```
contracts/       Orkos.sol — the on-chain enforcer, plus compiled ABI/bytecode
agent/           orkos_agent.py (Sibyl Memory decision layer), onchain.py (Base bridge)
scripts/         compile.js, deploy.py, run_demo.sh
tests/           test_agent.py — 5 tests covering recall, the delete-memory gate,
                 block/release/allow decisions
```

## License

MIT — see [LICENSE](./LICENSE).
