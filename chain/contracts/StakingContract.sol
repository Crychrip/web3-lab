// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title L2 staking and service-pass layer for DeAI (arXiv 2310.19099 §3.2)
contract StakingContract {
    uint256 public constant Q_NUM = 1;
    uint256 public constant Q_DEN = 10; // q = 0.1
    uint256 public constant FEE_BPS = 500; // 5% coordinator fee

    address public coordinator;

    mapping(address => uint256) public wallet;
    mapping(address => uint256) public nativeLocked;
    mapping(address => uint256) public otherLocked;
    mapping(address => bool) public hasPass;
    mapping(address => uint256) public minerRewards;

    uint256 public coordinatorFees;
    uint256 public totalLocked;

    event Faucet(address indexed user, uint256 amount);
    event Locked(
        address indexed client,
        uint256 amount,
        bool nativeAsset,
        uint256 effectiveStake
    );
    event Unlocked(address indexed client, uint256 nativeAmount, uint256 otherAmount);
    event PassIssued(address indexed client);
    event RewardCredited(address indexed miner, uint256 amount);
    event ChargedPay(
        address indexed client,
        address indexed miner,
        uint256 price,
        uint256 minerShare,
        uint256 fee
    );

    error NotCoordinator();
    error InvalidAmount();
    error InsufficientBalance();
    error NothingLocked();

    modifier onlyCoordinator() {
        if (msg.sender != coordinator) revert NotCoordinator();
        _;
    }

    constructor(address coordinator_) {
        coordinator = coordinator_;
    }

    function faucet(uint256 amount) external {
        if (amount == 0) revert InvalidAmount();
        wallet[msg.sender] += amount;
        emit Faucet(msg.sender, amount);
    }

    function lock(uint256 amount, bool nativeAsset) external {
        if (amount == 0) revert InvalidAmount();
        if (wallet[msg.sender] < amount) revert InsufficientBalance();
        wallet[msg.sender] -= amount;
        if (nativeAsset) {
            nativeLocked[msg.sender] += amount;
        } else {
            otherLocked[msg.sender] += amount;
        }
        totalLocked += amount;
        if (!hasPass[msg.sender]) {
            hasPass[msg.sender] = true;
            emit PassIssued(msg.sender);
        }
        emit Locked(msg.sender, amount, nativeAsset, weightOf(msg.sender));
    }

    function unlock() external {
        uint256 nativeAmount = nativeLocked[msg.sender];
        uint256 otherAmount = otherLocked[msg.sender];
        uint256 unlocked = nativeAmount + otherAmount;
        if (unlocked == 0) revert NothingLocked();
        nativeLocked[msg.sender] = 0;
        otherLocked[msg.sender] = 0;
        hasPass[msg.sender] = false;
        totalLocked -= unlocked;
        wallet[msg.sender] += unlocked;
        emit Unlocked(msg.sender, nativeAmount, otherAmount);
    }

    /// @notice Effective stake used as WRR input (native + q * other).
    function weightOf(address client) public view returns (uint256) {
        return nativeLocked[client] + (otherLocked[client] * Q_NUM) / Q_DEN;
    }

    function validPass(address client) external view returns (bool) {
        return hasPass[client] && weightOf(client) > 0;
    }

    function creditReward(address miner, uint256 amount) external onlyCoordinator {
        if (amount == 0) revert InvalidAmount();
        minerRewards[miner] += amount;
        emit RewardCredited(miner, amount);
    }

    function chargedPay(address miner, uint256 price) external {
        if (price == 0) revert InvalidAmount();
        if (wallet[msg.sender] < price) revert InsufficientBalance();
        uint256 fee = (price * FEE_BPS) / 10000;
        uint256 minerShare = price - fee;
        wallet[msg.sender] -= price;
        minerRewards[miner] += minerShare;
        coordinatorFees += fee;
        emit ChargedPay(msg.sender, miner, price, minerShare, fee);
    }
}
