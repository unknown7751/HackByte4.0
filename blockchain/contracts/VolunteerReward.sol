// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title VolunteerReward
 * @notice Distributes MATIC rewards to verified volunteers on the Polygon network.
 * @dev    Implements an Ownable pattern so only the backend (deployer/admin)
 *         can trigger reward transfers. A mapping prevents double-spending
 *         for the same taskId.
 *
 *  Deployment target: Polygon Amoy Testnet (chainId 80002)
 */
contract VolunteerReward {
    // ───────────────────────── State ─────────────────────────

    /// @notice Contract deployer / admin wallet (the backend hot-wallet).
    address public owner;

    /// @notice Fixed reward per task, in wei (default 0.01 MATIC).
    uint256 public rewardAmount;

    /// @notice Tracks which taskId has already been rewarded → prevents double-spend.
    mapping(string => bool) public completedTasks;

    // ───────────────────────── Events ────────────────────────

    /// @notice Emitted when a volunteer is successfully rewarded.
    event RewardSent(
        address indexed volunteer,
        string  taskId,
        uint256 amount,
        uint256 timestamp
    );

    /// @notice Emitted when the reward amount is changed by the owner.
    event RewardAmountUpdated(uint256 oldAmount, uint256 newAmount);

    /// @notice Emitted when the contract receives a MATIC deposit.
    event FundsDeposited(address indexed sender, uint256 amount);

    /// @notice Emitted when the owner withdraws remaining funds.
    event FundsWithdrawn(address indexed to, uint256 amount);

    // ───────────────────────── Modifiers ─────────────────────

    /// @dev Restricts function access to the contract owner.
    modifier onlyOwner() {
        require(msg.sender == owner, "VolunteerReward: caller is not the owner");
        _;
    }

    // ───────────────────────── Constructor ───────────────────

    /**
     * @param _rewardAmount Initial reward in wei. Pass 0.01 ether for 0.01 MATIC.
     */
    constructor(uint256 _rewardAmount) {
        require(_rewardAmount > 0, "VolunteerReward: reward must be > 0");
        owner = msg.sender;
        rewardAmount = _rewardAmount;
    }

    // ───────────────────────── Core ──────────────────────────

    /**
     * @notice Sends a fixed MATIC reward to a volunteer for completing a task.
     * @dev    Reverts if:
     *         - caller is not the owner
     *         - taskId has already been rewarded (double-spend guard)
     *         - volunteer address is zero
     *         - contract balance is insufficient
     * @param _volunteer The volunteer's wallet address.
     * @param _taskId    A unique identifier for the completed task.
     */
    function sendReward(
        address payable _volunteer,
        string memory _taskId
    ) external onlyOwner {
        // ── Guards ───────────────────────────────────────────
        require(_volunteer != address(0), "VolunteerReward: zero address");
        require(
            !completedTasks[_taskId],
            "VolunteerReward: task already rewarded"
        );
        require(
            address(this).balance >= rewardAmount,
            "VolunteerReward: insufficient contract balance"
        );

        // ── State change before transfer (Checks-Effects-Interactions) ──
        completedTasks[_taskId] = true;

        // ── Transfer ─────────────────────────────────────────
        (bool success, ) = _volunteer.call{value: rewardAmount}("");
        require(success, "VolunteerReward: MATIC transfer failed");

        emit RewardSent(_volunteer, _taskId, rewardAmount, block.timestamp);
    }

    // ───────────────────────── Admin helpers ─────────────────

    /**
     * @notice Update the reward amount. Only callable by the owner.
     * @param _newAmount New reward in wei.
     */
    function setRewardAmount(uint256 _newAmount) external onlyOwner {
        require(_newAmount > 0, "VolunteerReward: reward must be > 0");
        uint256 oldAmount = rewardAmount;
        rewardAmount = _newAmount;
        emit RewardAmountUpdated(oldAmount, _newAmount);
    }

    /**
     * @notice Withdraw remaining MATIC from the contract to the owner.
     */
    function withdrawFunds() external onlyOwner {
        uint256 balance = address(this).balance;
        require(balance > 0, "VolunteerReward: no funds to withdraw");
        (bool success, ) = payable(owner).call{value: balance}("");
        require(success, "VolunteerReward: withdrawal failed");
        emit FundsWithdrawn(owner, balance);
    }

    /**
     * @notice Transfer ownership to a new address (e.g. rotate the backend key).
     */
    function transferOwnership(address _newOwner) external onlyOwner {
        require(_newOwner != address(0), "VolunteerReward: zero address");
        owner = _newOwner;
    }

    /**
     * @notice Check the contract's MATIC balance.
     */
    function getBalance() external view returns (uint256) {
        return address(this).balance;
    }

    /**
     * @notice Check whether a task has already been rewarded.
     */
    function isTaskRewarded(string memory _taskId) external view returns (bool) {
        return completedTasks[_taskId];
    }

    // ───────────────────────── Receive ───────────────────────

    /// @notice Allow the contract to receive MATIC deposits.
    receive() external payable {
        emit FundsDeposited(msg.sender, msg.value);
    }

    /// @notice Fallback for calls with data that don't match a function.
    fallback() external payable {
        emit FundsDeposited(msg.sender, msg.value);
    }
}
