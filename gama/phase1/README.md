# FederHub – Group 3 (Team Gamma) | Phase 1: FedAvg Mock

## Overview

This directory contains the **Phase 1 deliverable** for Team Gamma (The Federated Engine).  
No network. No real clients. No gRPC. Just the math — exactly as scoped for Phase 1.

The goal is to implement and validate the core **Federated Averaging (FedAvg)** algorithm  
using hardcoded client weight arrays, forming the mathematical foundation that Phase 2  
will build real orchestration on top of.

---

## User Story Traceability

| File | Epic | Story | Acceptance Criteria |
|------|------|-------|---------------------|
| `fedavg_mock.py` | Epic 5 | 5.1 | Aggregator receives weights → executes FedAvg → produces new global model |
| `fedavg_mock.py` | Epic 2 | 2.3 | Server collects client updates → aggregates weights → global model updated per round |
| `test_fedavg.py` | Epic 5 | 5.1 | "Test the aggregation engine with simulated client arrays" (Confirmation) |

---

## Why Weighted FedAvg (not simple average)?

The original FedAvg paper (McMahan et al., 2017) weights each client's contribution  
**proportionally to their local dataset size**:

```
global_w[i] = Σ (n_k / n_total) * w_k[i]
```

A naive simple mean treats a client with 50 records the same as one with 5,000.  
Weighted averaging produces a fairer, more accurate global model — and directly  
matches the `Aggregation Service (FedAvg)` component in our system architecture diagram.

---

## Files

```
phase1-fedavg-mock/
├── fedavg_mock.py      # Core FedAvg implementation + mock round simulation
├── test_fedavg.py      # Unit tests (9 test cases, no external dependencies)
└── README.md           # This file
```

---

## How to Run

**Requirements:** Python 3.8+, no external packages needed.

### Run the mock aggregation:
```bash
python fedavg_mock.py
```

**Expected output:**
```
=======================================================
  FederHub - Federated Aggregation Mock | Round 1
=======================================================

[INPUT] Client Weight Updates Received:
  Client          Samples   Weights
  --------------- --------  ------------------------------
  Hospital A           300  ['0.1000', '0.2500', ...]
  Hospital B           500  ['0.1500', '0.2000', ...]
  Bank C               200  ['0.1200', '0.3000', ...]

[AGGREGATION] FedAvg applied across 3 clients.
  Total samples used : 1000
  Weight contributions:
    Hospital A      → 30.0% influence
    Hospital B      → 50.0% influence
    Bank C          → 20.0% influence

[OUTPUT] New Global Model Weights:
  ['0.129000', '0.230000', ...]

[STATUS] Aggregation complete. Global model ready for distribution.
=======================================================
```

### Run the tests:
```bash
python -m pytest test_fedavg.py -v
```

---

## Mock Client Scenario

| Client | Domain | Local Samples | Influence |
|--------|--------|--------------|-----------|
| Hospital A | Healthcare | 300 | 30% |
| Hospital B | Healthcare | 500 | 50% |
| Bank C | Finance | 200 | 20% |

These simulate the real-world use case from the FederHub project brief — organizations  
that **cannot share raw data** but can contribute model updates.

---

## Phase Roadmap

| Phase | Gamma Deliverable | Status |
|-------|------------------|--------|
| **Phase 1** | FedAvg mock script + Redis cloud setup | ✅ This PR |
| Phase 2 | Define `.proto` files, gRPC server stub | 🔜 Next |
| Phase 3 | Wire gRPC to real client weight streams | 🔜 |
| Phase 4 | End-to-end integration with Alpha & Beta | 🔜 |

---

## Branch Strategy

```
main
 └── dev
      └── feature/phase1-fedavg-mock  ← this branch
```

PR from `feature/phase1-fedavg-mock` → `dev` for team review,  
then `dev` → `main` after sprint sign-off.

---

## References

McMahan, H. B., et al. (2017). *Communication-Efficient Learning of Deep Networks  
from Decentralized Data*. AISTATS 2017. https://arxiv.org/abs/1602.05629