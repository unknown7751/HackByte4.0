"""
Standalone CLI script to send a volunteer reward using Web3.py.

Usage:
    python send_reward.py <volunteer_wallet> <task_id>

Example:
    python send_reward.py 0xABC123...DEF456 task-uuid-string-here

This script is useful for:
  • Manual reward distribution (outside the FastAPI backend)
  • Testing the blockchain connection
  • One-off reward recovery

Requirements:
    pip install web3 python-dotenv

Environment variables (from .env):
    WEB3_PROVIDER_URL        — Polygon Amoy RPC endpoint
    REWARD_CONTRACT_ADDRESS   — Deployed VolunteerReward contract
    DEPLOYER_PRIVATE_KEY      — Admin wallet private key
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path

from dotenv import load_dotenv
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware

# ─── Load .env from project root ──────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

# ─── Configuration ────────────────────────────────────────────
RPC_URL = os.getenv("WEB3_PROVIDER_URL", "https://rpc-amoy.polygon.technology")
CONTRACT_ADDRESS = os.getenv("REWARD_CONTRACT_ADDRESS", "")
PRIVATE_KEY = os.getenv("DEPLOYER_PRIVATE_KEY", "")

# ─── Minimal ABI ──────────────────────────────────────────────
ABI = [
    {
        "inputs": [
            {"internalType": "address payable", "name": "_volunteer", "type": "address"},
            {"internalType": "string", "name": "_taskId", "type": "string"},
        ],
        "name": "sendReward",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "string", "name": "_taskId", "type": "string"}],
        "name": "isTaskRewarded",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "getBalance",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "rewardAmount",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
]


def connect():
    """Establish a Web3 connection to Polygon Amoy."""
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

    if not w3.is_connected():
        print(f"❌ Cannot connect to RPC: {RPC_URL}")
        sys.exit(1)

    chain_id = w3.eth.chain_id
    print(f"🔗 Connected to chain {chain_id}")
    return w3


def send_reward(volunteer_wallet: str, task_id: str) -> str:
    """
    Sign and send a sendReward() transaction.

    Returns the transaction hash hex string.
    """
    # ── Validate config ───────────────────────────────────────
    if not CONTRACT_ADDRESS:
        print("❌ REWARD_CONTRACT_ADDRESS not set in .env")
        sys.exit(1)
    if not PRIVATE_KEY:
        print("❌ DEPLOYER_PRIVATE_KEY not set in .env")
        sys.exit(1)

    # ── Connect ───────────────────────────────────────────────
    w3 = connect()
    account = w3.eth.account.from_key(PRIVATE_KEY)
    print(f"🔑 Admin wallet: {account.address}")

    # ── Validate wallet address ───────────────────────────────
    if not Web3.is_address(volunteer_wallet):
        print(f"❌ Invalid wallet address: {volunteer_wallet}")
        sys.exit(1)

    volunteer_address = Web3.to_checksum_address(volunteer_wallet)

    # ── Contract instance ─────────────────────────────────────
    contract_address = Web3.to_checksum_address(CONTRACT_ADDRESS)
    contract = w3.eth.contract(address=contract_address, abi=ABI)

    # ── Pre-flight checks ─────────────────────────────────────
    # Check on-chain double-spend
    if contract.functions.isTaskRewarded(task_id).call():
        print(f"⚠️  Task '{task_id}' has already been rewarded on-chain.")
        sys.exit(0)

    # Check contract balance
    contract_balance = contract.functions.getBalance().call()
    reward_amount = contract.functions.rewardAmount().call()
    print(f"📄 Contract balance: {Web3.from_wei(contract_balance, 'ether')} MATIC")
    print(f"💰 Reward per task : {Web3.from_wei(reward_amount, 'ether')} MATIC")

    if contract_balance < reward_amount:
        print("❌ Contract balance is less than reward amount! Fund the contract first.")
        sys.exit(1)

    # Check admin balance (for gas)
    admin_balance = w3.eth.get_balance(account.address)
    print(f"🔑 Admin balance   : {Web3.from_wei(admin_balance, 'ether')} MATIC")

    if admin_balance < Web3.to_wei(0.001, "ether"):
        print("❌ Admin wallet balance too low for gas. Get Test MATIC from the faucet.")
        sys.exit(1)

    # ── Build transaction ─────────────────────────────────────
    nonce = w3.eth.get_transaction_count(account.address, "pending")
    chain_id = w3.eth.chain_id

    tx = contract.functions.sendReward(
        volunteer_address, task_id
    ).build_transaction({
        "chainId": chain_id,
        "from": account.address,
        "nonce": nonce,
        "gas": 200_000,
        "maxFeePerGas": w3.eth.gas_price * 2,
        "maxPriorityFeePerGas": Web3.to_wei(30, "gwei"),
    })

    # ── Sign & Send ───────────────────────────────────────────
    print(f"\n📤 Sending reward to {volunteer_address} for task '{task_id}'...")
    signed_tx = w3.eth.account.sign_transaction(tx, private_key=PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    tx_hash_hex = tx_hash.hex()
    print(f"   Transaction hash: {tx_hash_hex}")

    # ── Wait for confirmation ─────────────────────────────────
    print("⏳ Waiting for confirmation...")
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

    if receipt["status"] == 1:
        print(f"\n✅ Reward confirmed!")
        print(f"   Block number : {receipt['blockNumber']}")
        print(f"   Gas used     : {receipt['gasUsed']}")
        print(f"   Tx hash      : {tx_hash_hex}")
        print(f"\n🔍 View on PolygonScan Amoy:")
        print(f"   https://amoy.polygonscan.com/tx/0x{tx_hash_hex}")
    else:
        print(f"\n❌ Transaction reverted! Tx: {tx_hash_hex}")
        sys.exit(1)

    return tx_hash_hex


def check_status():
    """Print contract and admin wallet status."""
    if not CONTRACT_ADDRESS:
        print("❌ REWARD_CONTRACT_ADDRESS not set in .env")
        sys.exit(1)

    w3 = connect()
    contract_address = Web3.to_checksum_address(CONTRACT_ADDRESS)
    contract = w3.eth.contract(address=contract_address, abi=ABI)

    balance = contract.functions.getBalance().call()
    reward = contract.functions.rewardAmount().call()

    print(f"\n📄 Contract: {contract_address}")
    print(f"   Balance       : {Web3.from_wei(balance, 'ether')} MATIC")
    print(f"   Reward/task   : {Web3.from_wei(reward, 'ether')} MATIC")
    print(f"   Tasks fundable: {balance // reward if reward > 0 else 0}")

    if PRIVATE_KEY:
        account = w3.eth.account.from_key(PRIVATE_KEY)
        admin_balance = w3.eth.get_balance(account.address)
        print(f"\n🔑 Admin: {account.address}")
        print(f"   Balance       : {Web3.from_wei(admin_balance, 'ether')} MATIC")


def main():
    parser = argparse.ArgumentParser(
        description="SmartAccident — Volunteer Reward CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Send a reward:
    python send_reward.py send 0xABC...DEF task-uuid-here

  Check contract status:
    python send_reward.py status

  Check if a task has been rewarded:
    python send_reward.py check task-uuid-here
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # send
    send_parser = subparsers.add_parser("send", help="Send a reward to a volunteer")
    send_parser.add_argument("wallet", help="Volunteer's wallet address")
    send_parser.add_argument("task_id", help="Unique task identifier")

    # status
    subparsers.add_parser("status", help="Check contract and admin wallet status")

    # check
    check_parser = subparsers.add_parser("check", help="Check if a task has been rewarded")
    check_parser.add_argument("task_id", help="Task ID to check")

    args = parser.parse_args()

    if args.command == "send":
        send_reward(args.wallet, args.task_id)
    elif args.command == "status":
        check_status()
    elif args.command == "check":
        if not CONTRACT_ADDRESS:
            print("❌ REWARD_CONTRACT_ADDRESS not set in .env")
            sys.exit(1)
        w3 = connect()
        contract = w3.eth.contract(
            address=Web3.to_checksum_address(CONTRACT_ADDRESS), abi=ABI
        )
        rewarded = contract.functions.isTaskRewarded(args.task_id).call()
        print(f"Task '{args.task_id}': {'✅ Rewarded' if rewarded else '❌ Not rewarded'}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
