# AegisOT

### Unified OT Security Gateway for DNP3 & OPC UA Industrial Communication

---

## Project Overview

AegisOT is a Unified Operational Technology (OT) Security Gateway designed to secure communication between DNP3 and OPC UA industrial protocols.

The framework acts as an intermediary security layer that validates commands before they reach OT devices. It helps protect industrial environments against unauthorized operations, replay attacks, sequence manipulation, and excessive traffic while maintaining secure communication between legacy and modern systems.

---

## Architecture

The system consists of the following components:

* DNP3 Adapter – Handles DNP3 communication and forwards requests to the gateway.
* OPC UA Adapter – Handles OPC UA communication and forwards requests to the gateway.
* Gateway Core – Performs security validation and decision making.
* Redis Database – Stores sequence numbers, replay hashes, and rate-limiting information.
* Merkle Audit Logger – Creates tamper-evident audit records.
* Prometheus – Collects system metrics.
* Grafana – Visualizes security and performance metrics.
* LightSim – Simulated OT environment used for evaluation.

All traffic passes through the Gateway Core before reaching OT devices.

---

## Features

AegisOT provides the following security capabilities:

* Access Control List (ACL) Enforcement
* Replay Attack Detection
* Sequence Validation
* Rate Limiting
* Tamper-Evident Audit Logging
* Cross-Protocol Security Enforcement
* Real-Time Monitoring and Visualization
* Centralized Security Validation

---

## Installation

### Prerequisites

* Ubuntu 22.04 LTS
* Docker
* Docker Compose
* Python 3.x
* Git

### Setup

1. Clone the project repository.
git clone <repository_url>

2. Navigate to the project directory.
cd AegisOT

3. Start all services.
docker compose up -d

4. Verify that all containers are running.
docker compose ps

---

## Usage

1. Start the simulation environment.
2. Launch the DNP3 and OPC UA adapters.
3. Send commands from the simulated operator or client.
4. The Gateway Core validates each request.
5. Authorized commands are forwarded to the destination device.
6. Unauthorized commands are blocked and logged.

---

## Attack Testing

The framework was evaluated against multiple attack scenarios:

### Replay Attack

Previously captured packets are resent to test replay detection mechanisms.

### Unauthorized Command Injection

Commands originating from unauthorized sources are sent to verify ACL enforcement.

### Sequence Manipulation

Requests with invalid or out-of-order sequence numbers are transmitted to test sequence validation.

### Flooding / Rate-Limit Testing

Large volumes of requests are generated to evaluate rate-limiting capabilities.

### Expected Results

* Legitimate traffic is allowed.
* Malicious traffic is blocked.
* Security events are logged.
* Monitoring dashboards are updated in real time.

---

## Monitoring

### Prometheus

Prometheus collects system metrics including:

* Allowed Requests
* Blocked Requests
* Attack Attempts
* Gateway Activity
* System Performance

### Grafana

Grafana provides real-time dashboards for monitoring gateway operations and security events.

---

## Authors

AegisOT Development Team

* Danah Al-Muzel
* Najla Al-Yami
* Rana Al-Qahtani
* Najd Ghadra
* Shahad Al-Jaroudi

Department of Networks and Communications
College of Computer Science and Information Technology
Imam Abdulrahman Bin Faisal University

---

## License

This project was developed for academic and research purposes as part of the graduation project requirements at Imam Abdulrahman Bin Faisal University.

---

## Acknowledgments

We would like to thank our supervisor and the Department of Networks and Communications for their guidance and support throughout the development of this project.
