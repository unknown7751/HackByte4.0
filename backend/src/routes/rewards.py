"""
Reward routes — API endpoints for the blockchain reward system.

POST /api/v1/rewards/{task_id}/send   — Trigger on-chain reward for a verified task
GET  /api/v1/rewards/status           — Blockchain service health & balances
GET  /api/v1/rewards/{task_id}/check  — Check if a task has been rewarded
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.database import get_db
from src.models.task import Task
from src.models.volunteer import Volunteer
from src.services import (
    blockchain_service,
    BlockchainServiceError,
    InsufficientFundsError,
    TaskAlreadyRewardedError,
)

router = APIRouter(prefix="/rewards", tags=["Rewards"])


# ───────────────────────── Schemas ────────────────────────────

class RewardResponse(BaseModel):
    success: bool
    task_id: str
    volunteer_wallet: str
    transaction_hash: str | None = None
    message: str


class RewardStatusResponse(BaseModel):
    blockchain_available: bool
    contract_balance_matic: float | None = None
    admin_balance_matic: float | None = None
    reward_per_task_matic: float | None = None
    message: str


class TaskRewardCheckResponse(BaseModel):
    task_id: str
    rewarded_on_chain: bool | None = None
    reward_tx_hash: str | None = None
    message: str


# ───────────────────────── Endpoints ─────────────────────────

@router.post("/{task_id}/send", response_model=RewardResponse)
async def send_reward(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger a blockchain reward for a completed and verified task.

    Flow:
    1. Look up the task in the database.
    2. Verify the task status is 'verified' (admin has approved).
    3. Check if the task has already been rewarded (local DB + on-chain).
    4. Retrieve the volunteer's wallet address.
    5. Call sendReward() on the smart contract.
    6. Store the transaction hash in the database.
    """

    # ── 1. Fetch the task ─────────────────────────────────────
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found.",
        )

    # ── 2. Check task status ──────────────────────────────────
    if task.status != "verified":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Task status is '{task.status}'. Only 'verified' tasks can be rewarded.",
        )

    # ── 3. Local double-spend check ───────────────────────────
    if task.reward_tx_hash:
        return RewardResponse(
            success=True,
            task_id=str(task_id),
            volunteer_wallet="",
            transaction_hash=task.reward_tx_hash,
            message="Task was already rewarded. Returning existing tx hash.",
        )

    # ── 4. Get the volunteer's wallet ─────────────────────────
    vol_result = await db.execute(
        select(Volunteer).where(Volunteer.id == task.volunteer_id)
    )
    volunteer = vol_result.scalar_one_or_none()
    if volunteer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Volunteer not found.",
        )

    if not volunteer.wallet_address:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Volunteer has no wallet address registered.",
        )

    # ── 5. Check blockchain service ───────────────────────────
    if not blockchain_service.is_available:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Blockchain service is not configured. Check WEB3_PROVIDER_URL, "
                   "REWARD_CONTRACT_ADDRESS, and DEPLOYER_PRIVATE_KEY in .env.",
        )

    # ── 6. Send on-chain reward ───────────────────────────────
    task_id_str = str(task_id)  # Use the UUID string as the on-chain taskId

    try:
        tx_hash = blockchain_service.send_reward(
            volunteer_wallet=volunteer.wallet_address,
            task_id=task_id_str,
        )
    except TaskAlreadyRewardedError:
        # On-chain says it's done — update local DB to match
        task.reward_tx_hash = "already-rewarded-on-chain"
        await db.flush()
        return RewardResponse(
            success=True,
            task_id=task_id_str,
            volunteer_wallet=volunteer.wallet_address,
            message="Task was already rewarded on-chain (recovered).",
        )
    except InsufficientFundsError as e:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=str(e),
        )
    except BlockchainServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Blockchain error: {e}",
        )

    # ── 7. Persist the tx hash in the database ────────────────
    task.reward_tx_hash = tx_hash
    task.status = "rewarded"
    await db.flush()

    return RewardResponse(
        success=True,
        task_id=task_id_str,
        volunteer_wallet=volunteer.wallet_address,
        transaction_hash=tx_hash,
        message="Reward sent successfully!",
    )


@router.get("/status", response_model=RewardStatusResponse)
async def reward_status():
    """
    Check the health of the blockchain reward system:
    contract balance, admin balance, and reward amount.
    """
    if not blockchain_service.is_available:
        return RewardStatusResponse(
            blockchain_available=False,
            message="Blockchain service is not configured.",
        )

    try:
        return RewardStatusResponse(
            blockchain_available=True,
            contract_balance_matic=blockchain_service.get_contract_balance(),
            admin_balance_matic=blockchain_service.get_admin_balance(),
            reward_per_task_matic=blockchain_service.get_reward_amount(),
            message="Blockchain service is operational.",
        )
    except Exception as e:
        return RewardStatusResponse(
            blockchain_available=False,
            message=f"Error querying blockchain: {e}",
        )


@router.get("/{task_id}/check", response_model=TaskRewardCheckResponse)
async def check_task_reward(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Check whether a specific task has been rewarded (both local DB and on-chain).
    """
    task_id_str = str(task_id)

    # Check local DB
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()

    tx_hash = task.reward_tx_hash if task else None

    # Check on-chain
    on_chain = None
    if blockchain_service.is_available:
        try:
            on_chain = blockchain_service.check_task_rewarded_on_chain(task_id_str)
        except Exception:
            pass

    return TaskRewardCheckResponse(
        task_id=task_id_str,
        rewarded_on_chain=on_chain,
        reward_tx_hash=tx_hash,
        message="Reward check complete.",
    )
