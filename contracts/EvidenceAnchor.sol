// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title SkyForge EvidenceAnchor
/// @notice Anchors DO-178C verification evidence hashes on-chain for
///         tamper-evident traceability across requirements, coding and
///         verification activities.
/// @dev The evidence hash is the SHA-256 of the canonical JSON payload of an
///      evidence package produced by the SkyForge engine. Writing is open to
///      any submitter so that every verification run can be independently
///      anchored; on-chain timestamps are the source of truth for audit.
contract EvidenceAnchor {
    struct Evidence {
        bytes32 evidenceHash;
        address submitter;
        uint256 timestamp;
        string evidenceType;
        string metadataUri;
    }

    event EvidenceAnchored(
        bytes32 indexed evidenceHash,
        address indexed submitter,
        uint256 timestamp,
        string evidenceType,
        string metadataUri
    );

    /// @notice Anchor a new evidence hash. Reverts if already anchored.
    function anchor(
        bytes32 evidenceHash,
        string calldata evidenceType,
        string calldata metadataUri
    ) external returns (uint256 timestamp) {
        require(evidenceHash != bytes32(0), "EvidenceAnchor: empty hash");
        require(
            _evidences[evidenceHash].timestamp == 0,
            "EvidenceAnchor: already anchored"
        );

        timestamp = block.timestamp;
        _evidences[evidenceHash] = Evidence({
            evidenceHash: evidenceHash,
            submitter: msg.sender,
            timestamp: timestamp,
            evidenceType: evidenceType,
            metadataUri: metadataUri
        });
        _allHashes.push(evidenceHash);

        emit EvidenceAnchored(
            evidenceHash, msg.sender, timestamp, evidenceType, metadataUri
        );
    }

    /// @notice Check whether an evidence hash has been anchored.
    function verify(bytes32 evidenceHash) external view returns (bool) {
        return _evidences[evidenceHash].timestamp != 0;
    }

    /// @notice Full evidence record for a hash (zeroed if absent).
    function getEvidence(
        bytes32 evidenceHash
    ) external view returns (Evidence memory) {
        return _evidences[evidenceHash];
    }

    /// @notice Total number of anchored evidence hashes.
    function getHashCount() external view returns (uint256) {
        return _allHashes.length;
    }

    mapping(bytes32 => Evidence) private _evidences;
    bytes32[] private _allHashes;
}
