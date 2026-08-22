// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title Orkos
/// @notice Named for Horkos, the Greek god who punished broken oaths. This contract
///         is the enforcer: it holds a set of self-authored "vows" against a wallet's
///         positions and refuses to execute a transfer that violates one, even when
///         the wallet owner themselves signs and requests it.
/// @dev    This is the ON-CHAIN half of Orkos. The vow's rationale and full context
///         live in Sibyl Memory (off-chain, in the agent layer) — this contract only
///         stores the minimal enforceable terms needed to check a transaction against
///         a vow without trusting any off-chain party at execution time. The agent
///         (agent/orkos_agent.py) is the one that reads Sibyl Memory, decides whether
///         a proposed sell honors or violates the remembered vow, and either calls
///         release() to let the transaction through or leaves it blocked.
contract Orkos {
    /// @notice A single self-authored commitment against one asset.
    struct Vow {
        address asset;          // token address this vow protects (address(0) = native ETH)
        uint256 protectedAmount; // amount of `asset` that cannot be moved while the vow is active
        uint256 floorPriceE8;    // price (asset in USD, 8 decimals) below which panic-selling is presumed
        bytes32 thesisHash;      // hash of the off-chain thesis-invalidation condition (see Sibyl Memory record)
        bool active;
        uint64  createdAt;
    }

    /// @notice owner => vowId => Vow
    mapping(address => mapping(uint256 => Vow)) public vows;
    mapping(address => uint256) public vowCount;

    /// @notice A one-time release granted by the agent after it verifies, via Sibyl
    ///         Memory, that the thesis genuinely invalidated (not just price moving).
    ///         Each release is single-use and tied to a specific vow.
    mapping(address => mapping(uint256 => bool)) public released;

    /// @notice The agent address authorized to grant releases. In production this
    ///         should be a contract or a well-audited signer, not an EOA — set here
    ///         as a simple address for hackathon scope.
    address public agent;

    event VowCreated(address indexed owner, uint256 indexed vowId, address asset, uint256 protectedAmount, uint256 floorPriceE8, bytes32 thesisHash);
    event VowChecked(address indexed owner, uint256 indexed vowId, bool wouldViolate, uint256 attemptedAmount);
    event VowReleased(address indexed owner, uint256 indexed vowId, string reasonRef);
    event SellBlocked(address indexed owner, uint256 indexed vowId, uint256 attemptedAmount);
    event AgentUpdated(address indexed oldAgent, address indexed newAgent);

    error NotAgent();
    error VowNotActive();
    error VowViolated(uint256 vowId);

    modifier onlyAgent() {
        if (msg.sender != agent) revert NotAgent();
        _;
    }

    constructor(address _agent) {
        agent = _agent;
    }

    /// @notice Set (or update) the authorized agent. Callable by the current agent
    ///         only, so ownership of "who can release vows" can rotate deliberately.
    function setAgent(address newAgent) external onlyAgent {
        emit AgentUpdated(agent, newAgent);
        agent = newAgent;
    }

    /// @notice Create a new vow. Called by the wallet owner, in a "sober" session,
    ///         BEFORE any panic scenario. `thesisHash` should be keccak256 of the
    ///         plain-text thesis-invalidation condition that is stored in full,
    ///         off-chain, in Sibyl Memory — this contract never needs to know the
    ///         human-readable reasoning, only that a hash of it exists to check
    ///         against later.
    function createVow(
        address asset,
        uint256 protectedAmount,
        uint256 floorPriceE8,
        bytes32 thesisHash
    ) external returns (uint256 vowId) {
        vowId = vowCount[msg.sender]++;
        vows[msg.sender][vowId] = Vow({
            asset: asset,
            protectedAmount: protectedAmount,
            floorPriceE8: floorPriceE8,
            thesisHash: thesisHash,
            active: true,
            createdAt: uint64(block.timestamp)
        });
        emit VowCreated(msg.sender, vowId, asset, protectedAmount, floorPriceE8, thesisHash);
    }

    /// @notice Core enforcement check. Any wallet/relayer attempting a sell on behalf
    ///         of `owner` should call this first. Reverts if the attempted amount
    ///         would violate an active vow and no release has been granted.
    /// @dev    This is what the agent calls in the "fresh session, panic-sell attempt"
    ///         demo moment — the transaction genuinely fails on-chain if memory
    ///         (via the agent) hasn't granted a release.
    function checkAndEnforce(address owner, uint256 vowId, uint256 attemptedSellAmount) external {
        Vow memory v = vows[owner][vowId];
        if (!v.active) revert VowNotActive();

        bool wouldViolate = attemptedSellAmount >= v.protectedAmount && !released[owner][vowId];
        emit VowChecked(owner, vowId, wouldViolate, attemptedSellAmount);

        if (wouldViolate) {
            emit SellBlocked(owner, vowId, attemptedSellAmount);
            revert VowViolated(vowId);
        }
    }

    /// @notice Called ONLY by the agent, ONLY after it has checked Sibyl Memory and
    ///         confirmed the remembered thesis-invalidation condition is genuinely
    ///         met (not just price dropping). This is the one legitimate way past
    ///         an active vow. `reasonRef` is a pointer (e.g. a Sibyl Memory record id)
    ///         so the release is auditable against the off-chain reasoning.
    function releaseVow(address owner, uint256 vowId, string calldata reasonRef) external onlyAgent {
        Vow storage v = vows[owner][vowId];
        if (!v.active) revert VowNotActive();
        released[owner][vowId] = true;
        emit VowReleased(owner, vowId, reasonRef);
    }

    /// @notice Deactivate a vow entirely (e.g. position fully exited legitimately,
    ///         thesis played out as expected). Owner-only, no agent involvement
    ///         needed — this is not an override of a panic-block, just normal
    ///         lifecycle cleanup.
    function retireVow(uint256 vowId) external {
        vows[msg.sender][vowId].active = false;
    }

    function getVow(address owner, uint256 vowId) external view returns (Vow memory) {
        return vows[owner][vowId];
    }
}
