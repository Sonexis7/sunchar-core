import uuid
from datetime import datetime, timezone
from sunchar_core.ledger.merkle import SettlementMerkleTree, sha256_hash

def test_merkle_execution_and_proof():
    # Simulate 4 parallel batch executions finishing in the same settlement window
    records = []
    for i in range(4):
        rec = {
            "receipt_id": str(uuid.uuid4()),
            "tenant_id": "enterprise-corp-uk",
            "dispatched_at_utc": datetime.now(timezone.utc).isoformat(),
            "intensity_aef_gco2": 124.5,
            "intensity_mef_gco2": 450.0,
            "code_payload_hash": sha256_hash(f"print('run job {i}')"),
            "is_override": False
        }
        records.append(rec)

    # 1. Build Settlement Merkle Tree
    tree = SettlementMerkleTree(records)
    assert tree.root is not None
    print(f"Computed Settlement Block Merkle Root: {tree.root}")

    # 2. Extract single job proof for an external auditor
    target_leaf = tree.leaf_hashes[0]
    proof = tree.get_merkle_proof(target_leaf)
    print(f"Generated Audit Path Proof with {len(proof)} steps.")

    # 3. Verify the proof against the root (Auditor Verification)
    is_valid = SettlementMerkleTree.verify_proof(target_leaf, proof, tree.root)
    assert is_valid is True
    print("Auditor-Side Verification Test: PASS (Cryptographically Non-Repudiable)")

if __name__ == "__main__":
    test_merkle_execution_and_proof()
