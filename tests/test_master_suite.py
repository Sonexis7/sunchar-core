import sys
import subprocess
import time

TEST_MODULES = [
    ("Core Merkle Tree & Inclusion Proofs", "tests.test_merkle_core"),
    ("Pipeline Integration & SLA Invariants", "tests.test_pipeline_integration"),
    ("CISSP Hardening (Zero-Trust, BOLA, WORM)", "tests.test_cissp_hardening"),
    ("KMS Signatures & Hypervisor Attestation", "tests.test_kms_and_attestation"),
    ("Commercial E2E Simulation & Audit Pack PDF", "tests.test_e2e_commercial_demo"),
]

def run_master_suite():
    print("\n" + "=" * 70)
    print("      GREENOPS ENGINE v0.2.0 — MASTER PRE-COMMIT TEST HARNESS")
    print("=" * 70 + "\n")

    results = []
    overall_start = time.time()

    for label, module in TEST_MODULES:
        print(f"[*] Running: {label} ({module})...")
        t0 = time.time()
        res = subprocess.run([sys.executable, "-m", module], capture_output=True, text=True)
        duration = time.time() - t0

        if res.returncode == 0:
            print(f"    [+] PASS ({duration:.2f}s)\n")
            results.append((label, "PASS", duration, None))
        else:
            print(f"    [!] FAILED ({duration:.2f}s)\n")
            results.append((label, "FAIL", duration, res.stderr or res.stdout))

    total_duration = time.time() - overall_start

    print("\n" + "=" * 70)
    print("                     FINAL ASSURANCE AUDIT REPORT")
    print("=" * 70)
    
    all_passed = True
    for label, status, dur, err in results:
        status_str = f"[PASS]" if status == "PASS" else "[FAIL]"
        print(f" {status_str:<8} | {dur:6.2f}s | {label}")
        if status == "FAIL":
            all_passed = False
            print(f"\n--- Error Trace for {label} ---\n{err}\n")

    print("-" * 70)
    print(f"Total Test Duration: {total_duration:.2f}s")
    
    if all_passed:
        print("\n>>> VERDICT: ALL SYSTEMS COMPLIANT & HARDENED. READY FOR COMMIT. <<<\n")
        sys.exit(0)
    else:
        print("\n>>> VERDICT: TEST FAILURES DETECTED. DO NOT COMMIT. <<<\n")
        sys.exit(1)

if __name__ == "__main__":
    run_master_suite()
