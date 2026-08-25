"""
onchain.py

Bridges an agent decision (BLOCK / RELEASE) from orkos_agent.py to the real
Orkos.sol contract on Base. This is what makes the Base integration "real
work" rather than decoration: a RELEASE decision is not just printed to a
terminal, it is submitted as an actual transaction that changes contract
state, and a BLOCK decision means that transaction is never sent -- the
enforcement contract's `checkAndEnforce` would revert if anyone tried
anyway, so the money genuinely cannot move.

Fill in RPC_URL, ORKOS_ADDRESS, and AGENT_PRIVATE_KEY via environment
variables before running against a real network. Defaults point at Base
Sepolia testnet. NEVER commit a real private key -- use a .env file
(gitignored) or your shell environment.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from web3 import Web3

BASE_SEPOLIA_RPC = "https://sepolia.base.org"
ABI_PATH = Path(__file__).resolve().parent.parent / "contracts" / "Orkos.abi.json"


def get_web3(rpc_url: str | None = None) -> Web3:
    url = rpc_url or os.environ.get("ORKOS_RPC_URL", BASE_SEPOLIA_RPC)
    w3 = Web3(Web3.HTTPProvider(url))
    return w3


def load_abi() -> list[dict[str, Any]]:
    if not ABI_PATH.exists():
        raise FileNotFoundError(
            f"ABI not found at {ABI_PATH}. Compile Orkos.sol first "
            f"(see scripts/compile.sh) which writes the ABI here."
        )
    return json.loads(ABI_PATH.read_text())


def get_contract(w3: Web3, address: str | None = None):
    contract_address = address or os.environ.get("ORKOS_CONTRACT_ADDRESS")
    if not contract_address:
        raise ValueError(
            "No contract address set. Deploy Orkos.sol (scripts/deploy.py) "
            "and set ORKOS_CONTRACT_ADDRESS, or pass address= explicitly."
        )
    return w3.eth.contract(address=Web3.to_checksum_address(contract_address), abi=load_abi())


def submit_create_vow(
    asset_address: str,
    protected_amount: int,
    floor_price_e8: int,
    thesis_hash: str,
    rpc_url: str | None = None,
    contract_address: str | None = None,
) -> dict[str, Any]:
    """
    Creates a vow ON THE DEPLOYED CONTRACT -- called by the wallet owner
    (using DEPLOYER_PRIVATE_KEY here since we're using one wallet for both
    roles, per project setup) in a sober session, before any panic exists.
    This is the transaction that makes the whole system real on-chain,
    not just simulated in Python.
    """
    private_key = os.environ.get("DEPLOYER_PRIVATE_KEY")
    if not private_key:
        raise EnvironmentError("DEPLOYER_PRIVATE_KEY not set.")

    w3 = get_web3(rpc_url)
    contract = get_contract(w3, contract_address)
    owner_account = w3.eth.account.from_key(private_key)

    tx = contract.functions.createVow(
        Web3.to_checksum_address(asset_address), protected_amount, floor_price_e8, bytes.fromhex(thesis_hash.replace("0x", ""))
    ).build_transaction({
        "from": owner_account.address,
        "nonce": w3.eth.get_transaction_count(owner_account.address),
        "chainId": w3.eth.chain_id,
    })

    signed = w3.eth.account.sign_transaction(tx, private_key=private_key)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

    # vowId is the count *before* this vow was added -- read it from the event log
    vow_created_logs = contract.events.VowCreated().process_receipt(receipt)
    vow_id = vow_created_logs[0]["args"]["vowId"] if vow_created_logs else None

    return {
        "tx_hash": tx_hash.hex(),
        "status": "success" if receipt.status == 1 else "reverted",
        "block_number": receipt.blockNumber,
        "vow_id": vow_id,
        "owner": owner_account.address,
    }


def submit_release(
    owner_address: str,
    vow_id: int,
    reason_ref: str,
    rpc_url: str | None = None,
    contract_address: str | None = None,
) -> dict[str, Any]:
    """
    Called ONLY after orkos_agent.evaluate_sell_attempt() returns action=="RELEASE".
    Submits the real onchain transaction that unblocks the vow. `reason_ref`
    should be the Sibyl Memory record id / thesis_hash so the release is
    auditable back to the exact remembered reasoning that justified it.
    """
    private_key = os.environ.get("AGENT_PRIVATE_KEY")
    if not private_key:
        raise EnvironmentError(
            "AGENT_PRIVATE_KEY not set. This must be the key for the address "
            "passed as `agent` in the Orkos.sol constructor / setAgent()."
        )

    w3 = get_web3(rpc_url)
    contract = get_contract(w3, contract_address)
    agent_account = w3.eth.account.from_key(private_key)

    tx = contract.functions.releaseVow(
        Web3.to_checksum_address(owner_address), vow_id, reason_ref
    ).build_transaction({
        "from": agent_account.address,
        "nonce": w3.eth.get_transaction_count(agent_account.address),
        "chainId": w3.eth.chain_id,
    })

    signed = w3.eth.account.sign_transaction(tx, private_key=private_key)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

    return {
        "tx_hash": tx_hash.hex(),
        "status": "success" if receipt.status == 1 else "reverted",
        "block_number": receipt.blockNumber,
    }


def attempt_enforced_sell(
    owner_address: str,
    vow_id: int,
    attempted_amount: int,
    rpc_url: str | None = None,
    contract_address: str | None = None,
) -> dict[str, Any]:
    """
    Simulates what a wallet/relayer would call when actually trying to move
    funds. If no release has been granted for this vow, this call reverts
    on-chain -- this is the literal, provable "the money cannot move"
    moment for the demo, independent of anything the agent says off-chain.
    """
    w3 = get_web3(rpc_url)
    contract = get_contract(w3, contract_address)

    try:
        contract.functions.checkAndEnforce(
            Web3.to_checksum_address(owner_address), vow_id, attempted_amount
        ).call()
        return {"result": "WOULD_SUCCEED", "detail": "No active block -- transaction would proceed."}
    except Exception as e:
        return {"result": "WOULD_REVERT", "detail": str(e)}
