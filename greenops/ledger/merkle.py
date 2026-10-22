import hashlib
import json
from typing import List, Dict, Any, Optional

def sha256_hash(data: str) -> str:
    """Computes a SHA-256 hexadecimal hash string."""
    return hashlib.sha256(data.encode("utf-8")).hexdigest()

class SettlementMerkleTree:
    """
    Constructs a deterministic binary Merkle Tree over a 30-minute settlement block.
    Eliminates linear row-by-row locking by committing jobs in parallel,
    then computing a verifiable cryptographic root for the entire period.
    """
    def __init__(self, execution_records: List[Dict[str, Any]]):
        self.raw_records = execution_records
        self.leaf_hashes: List[str] = self._generate_leaf_hashes(execution_records)
        self.root: Optional[str] = self._build_merkle_root(self.leaf_hashes)

    def _generate_leaf_hashes(self, records: List[Dict[str, Any]]) -> List[str]:
        hashes = []
        for r in records:
            serialized = json.dumps({
                "receipt_id": str(r.get("receipt_id")),
                "tenant_id": str(r.get("tenant_id")),
                "dispatched_at_utc": str(r.get("dispatched_at_utc")),
                "intensity_aef_gco2": float(r.get("intensity_aef_gco2", 0.0)),
                "intensity_mef_gco2": float(r.get("intensity_mef_gco2", 0.0)),
                "code_payload_hash": str(r.get("code_payload_hash")),
                "is_override": bool(r.get("is_override", False))
            }, sort_keys=True)
            hashes.append(sha256_hash(serialized))
        return sorted(hashes)

    def _build_merkle_root(self, leaves: List[str]) -> Optional[str]:
        if not leaves:
            return None
        
        current_layer = leaves
        while len(current_layer) > 1:
            next_layer = []
            for i in range(0, len(current_layer), 2):
                left = current_layer[i]
                right = current_layer[i + 1] if i + 1 < len(current_layer) else left
                combined = sha256_hash(left + right)
                next_layer.append(combined)
            current_layer = next_layer

        return current_layer[0]

    def get_merkle_proof(self, target_leaf_hash: str) -> List[Dict[str, str]]:
        if target_leaf_hash not in self.leaf_hashes:
            raise ValueError("Target leaf hash not found in this settlement tree.")

        proof = []
        index = self.leaf_hashes.index(target_leaf_hash)
        current_layer = self.leaf_hashes[:]

        while len(current_layer) > 1:
            is_right_child = (index % 2 == 1)
            pair_index = index - 1 if is_right_child else index + 1

            if pair_index < len(current_layer):
                proof.append({
                    "position": "left" if is_right_child else "right",
                    "hash": current_layer[pair_index]
                })
            else:
                proof.append({
                    "position": "right",
                    "hash": current_layer[index]
                })

            index = index // 2
            next_layer = []
            for i in range(0, len(current_layer), 2):
                left = current_layer[i]
                right = current_layer[i + 1] if i + 1 < len(current_layer) else left
                next_layer.append(sha256_hash(left + right))
            current_layer = next_layer

        return proof

    @staticmethod
    def verify_proof(leaf_hash: str, proof: List[Dict[str, str]], expected_root: str) -> bool:
        current = leaf_hash
        for step in proof:
            sibling = step["hash"]
            if step["position"] == "left":
                current = sha256_hash(sibling + current)
            else:
                current = sha256_hash(current + sibling)
        return current == expected_root
