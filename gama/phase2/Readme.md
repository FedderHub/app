
# FederHub – Group 3 (Team Gamma) | Phase 2: gRPC Communication Bridge

## Overview: What We Did
This directory contains the **Phase 2 deliverable** for Team Gamma (The Federated Engine). 

Building upon the mathematical foundation established in Phase 1, Phase 2 implements the high-speed, bi-directional communication infrastructure required for a distributed machine learning platform. We transitioned from hardcoded, in-memory function calls to a fully serialized, network-ready architecture. 

Specifically, we:
1. Defined the strict data contracts using Protocol Buffers.
2. Built an asynchronous gRPC server to ingest streaming weight arrays.
3. Created a simulated client to push mock deep learning tensors.
4. Successfully integrated the Phase 1 `fedavg_mock.py` engine to calculate the new Master Model dynamically based on network payloads.

## Rationale: Why We Did It
Transmitting multi-megabyte (or gigabyte) arrays of machine learning tensors over standard REST APIs (HTTP/JSON) is highly inefficient, bloated, and prone to memory crashes. 

To build an enterprise-grade federated learning system, we implemented **gRPC** combined with **Protocol Buffers (Protobuf)**. Protobuf provides strict binary serialization, ensuring deep learning weights are compressed tightly, while gRPC multiplexing ensures low-latency transmission across the network. 

This directly satisfies **Epic 5, Story 5.1 / Tech Task G.1**: *Implement a bi-directional gRPC communication channel to securely transmit massive arrays of model weights.*

## Methodology: How We Did It
The implementation was executed in four sequential steps:

* **Schema Definition (`federation.proto`):** We defined the `WeightUpdate` message schema, strictly requiring `client_id`, `sample_count`, and a `repeated float` array for the model weights to guarantee data integrity.
* **Protobuf Compilation:** We utilized `grpc_tools.protoc` to generate the Python data access classes (`federation_pb2.py`) and the gRPC routing stubs (`federation_pb2_grpc.py`).
* **Server Implementation (`grpc_server.py`):** We built a threaded gRPC servicer listening on port 50051. It captures incoming weight streams in a thread-safe manner, extracts the data, and automatically triggers the Federated Averaging (FedAvg) calculation once all expected clients have reported in.
* **Client Simulation (`dummy_client.py`):** We built an independent script that connects to the server and pushes massive arrays of floats, proving that the infrastructure can handle edge-node interactions before Team Beta connects their live PyTorch models in Phase 3.
* **Integrity Validation (`test_grpc_bridge.py`):** We wrote Pytest unit tests to ensure that the floating-point precision of the mathematical tensors is not corrupted or truncated during the binary serialization/deserialization process.

## Validated Outputs
The system has been locally executed and verified. Below are the confirmed terminal outputs demonstrating the successful end-to-end Phase 2 flow.

### 1. Unit Testing (Serialization Integrity)
```bash
(venv) % python -m pytest test_grpc_bridge.py
====================== test session starts ======================
collected 1 item                                                                                                                         

test_grpc_bridge.py .                                      [100%]

======================= 1 passed in 0.07s =======================
```

### 2. Client Payload Transmission
```bash
(venv) % python dummy_client.py
[CLIENT] Hospital A sending local model update...
[CLIENT] Server Response: Update received from Hospital A successfully.

[CLIENT] Hospital B sending local model update...
[CLIENT] Server Response: Update received from Hospital B successfully.

[CLIENT] Bank C sending local model update...
[CLIENT] Server Response: Update received from Bank C successfully.
```

### 3. Server Ingestion & Aggregation
```bash
(venv) % python grpc_server.py
[SERVER] gRPC Aggregator listening on port 50051...
[SERVER] Received update from Hospital A (300 samples, 6 parameters).
[SERVER] Received update from Hospital B (500 samples, 6 parameters).
[SERVER] Received update from Bank C (200 samples, 6 parameters).

[SERVER] Target client count reached. Starting FedAvg aggregation...
[SERVER] Aggregation Successful! New Global Weights:
['0.129000', '0.235000', '0.394000', '0.479000', '0.581000', '0.706000']
```

