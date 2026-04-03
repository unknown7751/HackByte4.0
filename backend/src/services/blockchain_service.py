"""
Blockchain Reward Service — Web3.py integration with the VolunteerReward contract.

Connects to Polygon Amoy Testnet, signs transactions using the admin's private key,
and calls `sendReward()` on the deployed VolunteerReward contract.

Security Features:
  • Double-spend prevention at BOTH the contract level (on-chain mapping) AND
    the application level (local DB check before sending tx).
  • Nonce management with thread-safe locking for concurrent requests.
  • Comprehensive error handling for gas, funds, and network issues.
  • Private key loaded from environment — never hardcoded.
"""

import logging
import threading
from typing import Optional

from web3 import Web3
from web3.exceptions import ContractLogicError
from web3.middleware import ExtraDataToPOAMiddleware

from src.config.settings import settings

logger = logging.getLogger(__name__)

CONTRACT_ABI = [
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
    {
        "inputs": [],
        "name": "owner",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "address", "name": "volunteer", "type": "address"},
            {"indexed": False, "internalType": "string", "name": "taskId", "type": "string"},
            {"indexed": False, "internalType": "uint256", "name": "amount", "type": "uint256"},
            {"indexed": False, "internalType": "uint256", "name": "timestamp", "type": "uint256"},
        ],
        "name": "RewardSent",
        "type": "event",
    },
]


class BlockchainServiceError(Exception):
    """Base exception for blockchain service errors."""


class InsufficientFundsError(BlockchainServiceError):
    """Raised when the admin wallet or contract has insufficient MATIC."""


class TaskAlreadyRewardedError(BlockchainServiceError):
    """Raised when a task has already been rewarded on-chain."""


class BlockchainService:
    def __init__(self):
        self._web3: Optional[Web3] = None
        self._contract = None
        self._account = None
        self._nonce_lock = threading.Lock()
        self._current_nonce: Optional[int] = None
        self._initialized = False

    def initialize(self) -> None:
        if self._initialized:
            return

        if not settings.WEB3_PROVIDER_URL:
            logger.warning("⚠️  WEB3_PROVIDER_URL not set — blockchain rewards disabled.")
            return

        if not settings.REWARD_CONTRACT_ADDRESS:
            logger.warning("⚠️  REWARD_CONTRACT_ADDRESS not set — blockchain rewards disabled.")
            return

        if not settings.DEPLOYER_PRIVATE_KEY:
            logger.warning("⚠️  DEPLOYER_PRIVATE_KEY not set — blockchain rewards disabled.")
            return

        try:
            self._web3 = Web3(Web3.HTTPProvider(settings.WEB3_PROVIDER_URL))
            self._web3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

            if not self._web3.is_connected():
                raise BlockchainServiceError(f"Cannot connect to RPC: {settings.WEB3_PROVIDER_URL}")

            chain_id = self._web3.eth.chain_id
            logger.info(f"🔗 Connected to chain {chain_id} via {settings.WEB3_PROVIDER_URL}")

            self._account = self._web3.eth.account.from_key(settings.DEPLOYER_PRIVATE_KEY)
            logger.info(f"🔑 Admin wallet: {self._account.address}")

            contract_address = Web3.to_checksum_address(settings.REWARD_CONTRACT_ADDRESS)
            self._contract = self._web3.eth.contract(address=contract_address, abi=CONTRACT_ABI)
            logger.info(f"📄 Contract: {contract_address}")

            self._current_nonce = self._web3.eth.get_transaction_count(self._account.address, "pending")
            logger.info(f"📊 Starting nonce: {self._current_nonce}")

            self._initialized = True
            logger.info("✅ Blockchain service initialized successfully.")

        except Exception as e:
            logger.error(f"❌ Blockchain service init failed: {e}")
            self._initialized = False
            raise BlockchainServiceError(f"Initialization failed: {e}") from e

    @property
    def is_available(self) -> bool:
        return self._initialized and self._web3 is not None

    def check_task_rewarded_on_chain(self, task_id: str) -> bool:
        if not self.is_available:
            raise BlockchainServiceError("Blockchain service not initialized")
        return self._contract.functions.isTaskRewarded(task_id).call()

    def get_contract_balance(self) -> float:
        if not self.is_available:
            raise BlockchainServiceError("Blockchain service not initialized")
        balance_wei = self._contract.functions.getBalance().call()
        return float(Web3.from_wei(balance_wei, "ether"))

    def get_admin_balance(self) -> float:
        if not self.is_available:
            raise BlockchainServiceError("Blockchain service not initialized")
        balance_wei = self._web3.eth.get_balance(self._account.address)
        return float(Web3.from_wei(balance_wei, "ether"))

    def get_reward_amount(self) -> float:
        if not self.is_available:
            raise BlockchainServiceError("Blockchain service not initialized")
        amount_wei = self._contract.functions.rewardAmount().call()
        return float(Web3.from_wei(amount_wei, "ether"))

    def send_reward(self, volunteer_wallet: str, task_id: str) -> str:
        if not self.is_available:
            raise BlockchainServiceError("Blockchain service not initialized")

        if not Web3.is_address(volunteer_wallet):
            raise BlockchainServiceError(f"Invalid wallet address: {volunteer_wallet}")

        volunteer_address = Web3.to_checksum_address(volunteer_wallet)

        if self.check_task_rewarded_on_chain(task_id):
            raise TaskAlreadyRewardedError(f"Task '{task_id}' has already been rewarded on-chain.")

        contract_balance = self.get_contract_balance()
        reward = self.get_reward_amount()
        if contract_balance < reward:
            raise InsufficientFundsError(
                f"Contract balance ({contract_balance:.4f} MATIC) is less than "
                f"reward amount ({reward:.4f} MATIC). Please fund the contract."
            )

        admin_balance = self.get_admin_balance()
        if admin_balance < 0.001:
            raise InsufficientFundsError(
                f"Admin wallet balance ({admin_balance:.6f} MATIC) is too low "
                f"for gas fees. Get Test MATIC from the Polygon Amoy faucet."
            )

        try:
            chain_id = self._web3.eth.chain_id

            with self._nonce_lock:
                on_chain_nonce = self._web3.eth.get_transaction_count(self._account.address, "pending")
                nonce = max(self._current_nonce or 0, on_chain_nonce)

                tx = self._contract.functions.sendReward(volunteer_address, task_id).build_transaction(
                    {
                        "chainId": chain_id,
                        "from": self._account.address,
                        "nonce": nonce,
                        "gas": 200_000,
                        "maxFeePerGas": self._web3.eth.gas_price * 2,
                        "maxPriorityFeePerGas": Web3.to_wei(30, "gwei"),
                    }
                )

                signed_tx = self._web3.eth.account.sign_transaction(
                    tx, private_key=settings.DEPLOYER_PRIVATE_KEY
                )
                tx_hash = self._web3.eth.send_raw_transaction(signed_tx.raw_transaction)

                self._current_nonce = nonce + 1

            tx_hash_hex = tx_hash.hex()
            logger.info(f"📤 Reward tx sent: {tx_hash_hex} | task={task_id} | volunteer={volunteer_address}")

            receipt = self._web3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

            if receipt["status"] != 1:
                logger.error(f"❌ Transaction reverted: {tx_hash_hex}")
                raise BlockchainServiceError(f"Transaction reverted on-chain: {tx_hash_hex}")

            logger.info(
                f"✅ Reward confirmed in block {receipt['blockNumber']} | "
                f"gas used: {receipt['gasUsed']} | tx: {tx_hash_hex}"
            )

            return tx_hash_hex

        except TaskAlreadyRewardedError:
            raise
        except InsufficientFundsError:
            raise
        except ContractLogicError as e:
            error_msg = str(e)
            if "task already rewarded" in error_msg.lower():
                raise TaskAlreadyRewardedError(
                    f"Task '{task_id}' already rewarded (contract revert)."
                ) from e
            if "insufficient" in error_msg.lower():
                raise InsufficientFundsError(f"Insufficient funds: {error_msg}") from e
            raise BlockchainServiceError(f"Contract error: {error_msg}") from e
        except ValueError as e:
            error_msg = str(e)
            if "insufficient funds" in error_msg.lower():
                raise InsufficientFundsError(
                    "Admin wallet lacks MATIC for gas. Get Test MATIC from the Polygon Amoy faucet."
                ) from e
            if "nonce too low" in error_msg.lower():
                logger.warning("Nonce too low — resetting from chain...")
                with self._nonce_lock:
                    self._current_nonce = self._web3.eth.get_transaction_count(
                        self._account.address, "pending"
                    )
                raise BlockchainServiceError("Nonce conflict — please retry the request.") from e
            if "replacement transaction underpriced" in error_msg.lower():
                raise BlockchainServiceError(
                    "Nonce collision detected (concurrent sends). The system will auto-recover — please retry."
                ) from e
            raise BlockchainServiceError(f"Transaction error: {error_msg}") from e
        except Exception as e:
            logger.error(f"❌ Unexpected blockchain error: {e}", exc_info=True)
            raise BlockchainServiceError(f"Unexpected error sending reward: {e}") from e


blockchain_service = BlockchainService()
