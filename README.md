# TankerNet - Water Tanker Quality & Delivery Verification System

TankerNet is a serverless backend for verifying urban water tanker logistics and water quality. It safeguards municipal water supply networks against contamination and arbitrary tariff spikes using AWS Serverless Application Model (SAM), Amazon Bedrock, AWS IoT Core, and Amazon DynamoDB.

---

## Key Features

1. **Multilingual AI Booking Extraction**: Accepts free-text booking messages in **Hindi, English, Hinglish, and Punjabi** (both Gurmukhi script and Romanized Punjabi). Amazon Bedrock parses volume, location, and urgency, with a zero-dependency deterministic local NLP fallback.
2. **City-Scoped Haversine Dispatch**: Geocodes locations across 3 major metropolitan cities (**Delhi, Mumbai, Bengaluru**) and dispatches the nearest `IDLE` tanker strictly within the same city.
3. **Automated Quality Telemetry & Valve Lock**: Ingests real-time IoT water quality sensors (TDS and Turbidity).
   - If $\text{TDS} > 500\text{ ppm}$ or $\text{Turbidity} > 5.0\text{ NTU}$, the valve is automatically locked and the tanker is marked `FLAGGED`.
   - If water quality normalizes ($\text{TDS} \le 500$, $\text{Turbidity} \le 5$), the tanker status clears back to `IN_TRANSIT`, but the **valve remains locked** until an authorized delivery unlock.
4. **Three-Factor Delivery Verification**: Unlocks the delivery valve only when:
   - The customer's 6-digit OTP matches.
   - The tanker's GPS is within **20 meters** of the registered delivery coordinates.
   - The latest water parameters satisfy $\text{TDS} \le 500\text{ ppm}$ and $\text{Turbidity} \le 5.0\text{ NTU}$.
5. **Certified Quality Receipts**: Issues a cryptographic delivery receipt strictly stating that water parameters are **"within limits"** (compliance requirement: the word *"safe"* is never used).
6. **Fleet Health Metrics & Illustrative Price Caps**: Provides city administrators with real-time green/red fleet status and regulatory price caps categorized by booking urgency.

---

## Architecture

```
                  +----------------------------------------------+
                  |         Citizen / Resident App               |
                  +----------------------------------------------+
                                         |
                                (HTTP REST APIs)
                                         v
+---------------------------------------------------------------------------------+
|                                 API Gateway                                     |
+---------------------------------------------------------------------------------+
     |                     |                      |                 |           |
 (POST booking)     (POST telemetry)      (POST unlock)       (GET receipt) (GET admin)
     v                     v                      v                 v           v
[Booking Lambda]   [Telemetry Lambda]     [Unlock Lambda]     [Receipt]    [Admin]
     |                     ^                      |                 |           |
  (Bedrock/            (IoT Rule:                 v                 v           v
   NLP Fallback)    tanker/+/telemetry)      (Verify OTP,      [Receipts   [Tankers
     |                                        20m Geofence,      Table]      Table]
     v                                         TDS <= 500)
[Geocode 3-Cities]                                |
     |                                     (Publish MQTT)
     v                                            v
[Tankers & Bookings]                     [tanker/{id}/valve]
```

---

## 3 Cities & Coverage Areas

Tankers are seeded across three major metropolitan cities, and bookings are strictly matched with tankers in the customer's city:

| City | Supported Areas | Reference Coordinates | Initial Seeded Tankers |
| :--- | :--- | :--- | :--- |
| **Delhi** | Dwarka Sec 10, Saket, Lajpat Nagar, Mehrauli | Saket: `28.5244, 77.2066` | `TANKER-DEL-01`, `TANKER-DEL-02` |
| **Mumbai** | Mankhurd, Govandi, Kurla, Andheri East | Kurla: `19.0726, 72.8845` | `TANKER-BOM-01`, `TANKER-BOM-02` |
| **Bengaluru** | Whitefield, Bellandur, Koramangala, Indiranagar | Koramangala: `12.9352, 77.6245` | `TANKER-BLR-01`, `TANKER-BLR-02` |

---

## DynamoDB Tables

### 1. `Tankers` (`TankerNet-Tankers`)
- **Partition Key**: `tanker_id` (String, e.g. `TANKER-DEL-01`)
- **Attributes**: `driver_name`, `city`, `current_location` (`{lat, lng}`), `tds_level`, `turbidity_level`, `valve_locked` (bool), `status` (`IDLE` | `IN_TRANSIT` | `DELIVERING` | `FLAGGED`).

### 2. `Bookings` (`TankerNet-Bookings`)
- **Partition Key**: `booking_id` (String, e.g. `BOOK-9A8B7C`)
- **Attributes**: `user_name`, `city`, `delivery_location` (`{lat, lng}`), `volume_liters`, `status` (`PENDING` | `DISPATCHED` | `COMPLETED` | `CANCELLED`), `assigned_tanker_id`, `otp` (6 digits).

### 3. `Receipts` (`TankerNet-Receipts`)
- **Partition Key**: `booking_id` (String)
- **Attributes**: `tanker_id`, `fill_time`, `delivery_time`, `tds`, `turbidity`, `quality_statement` (*"Water quality parameters are within limits (TDS: 375 ppm, Turbidity: 1.4 NTU)"*), `verification_metrics`.

---

## API Endpoints

### 1. Create Booking
`POST /api/booking/create`

Accepts free text in Hindi, English, Hinglish, or Punjabi (Gurmukhi or Romanized):
```json
{
  "text": "ਮੈਨੂੰ ਲਾਜਪਤ ਨਗਰ ਵਿੱਚ 5000 ਲੀਟਰ ਪਾਣੀ ਚਾਹੀਦਾ ਹੈ ਤੁਰੰਤ",
  "user_name": "Gurpreet Singh"
}
```

Response (`201 Created`):
```json
{
  "message": "Booking created successfully",
  "booking": {
    "booking_id": "BOOK-71A49B1F",
    "user_name": "Gurpreet Singh",
    "city": "Delhi",
    "delivery_area": "Lajpat Nagar",
    "delivery_location": {"lat": 28.5677, "lng": 77.2433},
    "volume_liters": 5000,
    "urgency": "HIGH",
    "status": "DISPATCHED",
    "assigned_tanker_id": "TANKER-DEL-01",
    "otp": "481923"
  }
}
```

### 2. Ingest Telemetry
`POST /api/tanker/telemetry` *(Also invoked automatically via AWS IoT Topic Rule for `tanker/+/telemetry`)*
```json
{
  "tanker_id": "TANKER-DEL-01",
  "lat": 28.5580,
  "lng": 77.2370,
  "tds": 385,
  "turbidity": 1.7
}
```

- If $\text{TDS} > 500$ or $\text{Turbidity} > 5.0$: `status` becomes `FLAGGED`, `valve_locked` set to `true`.
- If readings normalize ($\text{TDS} \le 500$ and $\text{Turbidity} \le 5$): `status` clears back to `IN_TRANSIT`, while `valve_locked` **remains `true`**.

### 3. Unlock Tanker Valve
`POST /api/tanker/unlock`
```json
{
  "booking_id": "BOOK-71A49B1F",
  "tanker_id": "TANKER-DEL-01",
  "user_otp": "481923"
}
```

Requires:
1. Valid 6-digit OTP matching the booking.
2. Distance between tanker and delivery location $\le 20\text{ meters}$.
3. Latest $\text{TDS} \le 500\text{ ppm}$ and status not `FLAGGED`.

### 4. Quality Receipt
`GET /api/receipt/{booking_id}`

Response (`200 OK`):
```json
{
  "message": "Quality receipt retrieved successfully",
  "receipt": {
    "booking_id": "BOOK-71A49B1F",
    "tanker_id": "TANKER-DEL-01",
    "tds": 375,
    "turbidity": 1.4,
    "quality_statement": "Water quality parameters are within limits (TDS: 375 ppm, Turbidity: 1.4 NTU)",
    "verification_metrics": {
      "otp_verified": true,
      "distance_meters": 3.48,
      "geofence_verified": true,
      "quality_verified": true
    }
  }
}
```

### 5. Admin Metrics
`GET /api/admin/metrics`

Returns fleet overview (total, active, healthy green, flagged red), city breakdowns, and regulatory price caps.

> [!NOTE]
> **Illustrative Reference Price Caps**:
> The price caps returned by `/api/admin/metrics` are **illustrative benchmark values** per 1,000L to guide maximum municipal tariffs during scarcity:
> - **LOW urgency** (standard 24-48h): ₹500 / 1,000L (1.0x base)
> - **MEDIUM urgency** (same-day priority): ₹600 / 1,000L (1.2x)
> - **HIGH urgency** (emergency immediate dispatch): ₹750 / 1,000L (1.5x)

---

## Local Testing with Pytest

The entire system is equipped with an in-memory mock database and local NLP fallback parser, requiring zero AWS credentials to execute.

1. Install test dependencies:
   ```bash
   pip install -r requirements-dev.txt
   ```

2. Run the complete test suite:
   ```bash
   pytest -v
   ```

3. Test coverage includes:
   - `tests/test_geo.py`: Haversine calculation, geofencing threshold ($20\text{ m}$ boundary check), nearest tanker lookup.
   - `tests/test_bedrock_parser.py`: Multi-language extraction (Gurmukhi Punjabi, Romanized Punjabi, Hindi, Hinglish, English).
   - `tests/test_telemetry.py`: Contamination thresholds and `FLAGGED` recovery logic (valve lock persistence).
   - `tests/test_unlock.py`: Multi-condition unlock verification (OTP, geofence, water quality) and failure scenarios.
   - `tests/test_receipt.py`: Wording validation (asserts *"within limits"*, forbids *"safe"*).
   - `tests/test_admin.py`: Fleet metrics and illustrative price caps.
   - `tests/test_e2e_flow.py`: Complete lifecycle from booking to receipt.

---

## Running the Tanker Simulator

A simulation script models a live delivery run along the route: **Saket $\rightarrow$ Lajpat Nagar (Delhi)**:

```bash
python simulate_tanker.py
```

### Simulation Phases:
1. **Saket Departure**: Baseline clean water ($\text{TDS}=380$).
2. **Pushp Vihar**: Normal transit.
3. **Chirag Dilli (Spike)**: Contamination injected ($\text{TDS}=555\text{ ppm}$, $\text{Turbidity}=5.8\text{ NTU}$). Triggers `FLAGGED` status and automatic valve lock.
4. **Andrews Ganj (Recovery)**: Flush/filtration recovery ($\text{TDS}=385\text{ ppm}$, within 350-420 ppm). Tanker resets to `IN_TRANSIT` while valve securely remains locked.
5. **Lajpat Nagar Arrival**: Vehicle parks within 3.5 meters ($\le 20\text{ m}$) of customer coordinates, ready for customer OTP unlock.

---

## Local Testing with AWS SAM Local & LocalStack

### Using SAM Local
Start local API Gateway emulation:
```bash
sam local start-api --port 3000
```

### Using LocalStack
To run with LocalStack for local DynamoDB and IoT Core:
```bash
# 1. Start LocalStack
docker run -p 4566:4566 -e SERVICES=dynamodb,iot,iot-data localstack/localstack

# 2. Configure environment variables in env.json
# DYNAMODB_ENDPOINT: "http://localhost:4566"
# IOT_ENDPOINT: "http://localhost:4566"
```

---

## AWS Deployment (Production)

Deploy using the AWS SAM CLI without hardcoded credentials:

```bash
# 1. Build serverless artifacts
sam build

# 2. Deploy guided
sam deploy --guided
```

The SAM template will provision:
- API Gateway with CORS enabled.
- 5 Python 3.12 Lambda functions.
- 3 on-demand DynamoDB tables (`Tankers`, `Bookings`, `Receipts`).
- AWS IoT Core Topic Rule routing `tanker/+/telemetry` directly to the Telemetry Lambda.
- Least-privilege IAM roles and execution policies.

## AWS open source tools used
- AWS SAM CLI: template.yaml defines API Gateway, 5 Lambda functions,
  3 DynamoDB tables and an IoT Core rule. `sam build` succeeds locally.
- Target AWS services: Lambda, DynamoDB, IoT Core, Amazon Bedrock.
- Not deployed to AWS (no account). Verified locally with 24 pytest tests.
- Template runtime was set to python3.14 for local build; use
  python3.12 (or a Lambda-supported runtime) when deploying.