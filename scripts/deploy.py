"""
deploy.py

Deploys Orkos.sol to Base Sepolia testnet. Requires:
  - DEPLOYER_PRIVATE_KEY  (env var -- the wallet that deploys, becomes contract creator)
  - AGENT_ADDRESS         (env var -- the address authorized to call releaseVow())
  - Contract already compiled: run `node scripts/compile.js` first.

Get free Base Sepolia ETH from a faucet before running this (search "Base
Sepolia faucet"). This is testnet-only -- no real funds are ever at risk.

Usage:
    export DEPLOYER_PRIVATE_KEY=0x...
    export AGENT_ADDRESS=0x...
    python3 scripts/deploy.py
"""

import json
import os
import sys
from pathlib import Path

from web3 import Web3

ROOT = Path(__file__).resolve().parent.parent
BASE_SEPOLIA_RPC = "https://sepolia.base.org"


def main():
    private_key = os.environ.get("DEPLOYER_PRIVATE_KEY")
    agent_address = os.environ.get("AGENT_ADDRESS")

    if not private_key or not agent_address:
        print("ERROR: set DEPLOYER_PRIVATE_KEY and AGENT_ADDRESS env vars first.")
        sys.exit(1)

    abi_path = ROOT / "contracts" / "Orkos.abi.json"
    bytecode_path = ROOT / "contracts" / "Orkos.bytecode.txt"

    if not abi_path.exists() or not bytecode_path.exists():
        print("ERROR: contract not compiled. Run: node scripts/compile.js")
        sys.exit(1)

    abi = json.loads(abi_path.read_text())
    bytecode = bytecode_path.read_text().strip()

    w3 = Web3(Web3.HTTPProvider(os.environ.get("ORKOS_RPC_URL", BASE_SEPOLIA_RPC)))
    deployer = w3.eth.account.from_key(private_key)

    print(f"Deploying from: {deployer.address}")
    print(f"Agent address:  {agent_address}")
    print(f"RPC:            {w3.provider.endpoint_uri}")

    balance = w3.eth.get_balance(deployer.address)
    print(f"Deployer balance: {w3.from_wei(balance, 'ether')} ETH")
    if balance == 0:
        print("WARNING: zero balance. Fund this address from a Base Sepolia faucet first.")
        sys.exit(1)

    Contract = w3.eth.contract(abi=abi, bytecode=bytecode)
    tx = Contract.constructor(Web3.to_checksum_address(agent_address)).build_transaction({
        "from": deployer.address,
        "nonce": w3.eth.get_transaction_count(deployer.address),
        "chainId": w3.eth.chain_id,
    })

    signed = w3.eth.account.sign_transaction(tx, private_key=private_key)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    print(f"Deploy tx sent: {tx_hash.hex()}")
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

    print(f"\nDeployed at: {receipt.contractAddress}")
    print(f"Block:       {receipt.blockNumber}")
    print(f"\nSet this for the rest of the demo:")
    print(f"  export ORKOS_CONTRACT_ADDRESS={receipt.contractAddress}")


if __name__ == "__main__":
    main()
