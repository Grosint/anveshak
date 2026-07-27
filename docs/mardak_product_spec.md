# MARDAK (मर्दक) — Tactical BLE Mesh Disruption System

## Product Overview

**MARDAK** = Suppressor. Turnkey BLE mesh disruption system for LEAs. Neutralizes peer-to-peer messaging apps (Bridgefy, BitChat, etc.) at protest sites where internet is already shut down via ISP cooperation.

**Relationship to Anveshak:** Anveshak = upstream OSINT intelligence (pre/post event monitoring). MARDAK = tactical BLE disruption. Separate product lines. Integration planned in Phase 4.

## Problem Statement

Bluetooth mesh messaging apps (BitChat, Bridgefy) enable P2P communication without cellular/Wi-Fi. Internet shutdowns become ineffective. LEAs need a way to disrupt these mesh networks without collateral damage to their own communications.

## Attack Method

### Strategy: BDoS-first, RF Jamming as Escalation Only

**Primary — Connection Request Storm (Layer 2):**
- Send CONNECT_IND to every advertising BLE device
- Never complete handshake — target phone's BLE radio locked for supervision timeout (~6s per attempt)
- 7 nRF52840 dongles with custom firmware × ~50-100 devices/second = ~350-700 devices/second locked out
- Each dongle runs attack logic on its own ARM Cortex-M4F — RPi only sends start/stop commands
- Steady state: ~2000-4000 devices simultaneously locked

**Secondary — Advertisement Flood (Layer 2):**
- Blast ADV_NONCONN_IND packets at max rate on channels 37, 38, 39 via 2 dedicated dongles
- ~10,000+ packets/sec per dongle (direct radio register access, no kernel overhead)
- Random MAC per packet (instant rotation via custom firmware)
- Saturates discovery channels — new mesh links can't form

**Advanced Attacks (unlocked by nRF52840 custom firmware):**
- Selective jamming: carrier wave on advertisement channels only, data channels untouched
- Malformed packet injection: invalid length/CRC packets crash poorly-written BLE stacks
- Extended supervision lock: precisely timed partial handshake packets extend lock beyond 6s
- BLE 5.0 extended advertisement targeting: attacks newer Android phones using BLE 5.0

**App-agnostic:** Attacks BLE protocol layer, not app-specific packets. Works against any BLE mesh app without knowing which app is in use.

**RF Jamming:** Escalation option only (Phase 5). BDoS preferred because:
- Covert — looks like network congestion, not intentional jamming
- No collateral to LEA equipment or civilian medical devices
- COTS deployable

## Hardware — Field Unit (MARDAK F1)

| Component | Spec | Source |
|-----------|------|--------|
| Raspberry Pi 4 (4GB) | ARM Cortex-A72 | Robu.in / Amazon.in |
| nRF52840 MDK USB Dongle × 7 | Nordic nRF52840 SoC, BLE 5.0, ARM Cortex-M4F, 256KB RAM, 1MB Flash, custom attack firmware | fabtolab.com (₹2,592 each) |
| Powered USB hub (7-port) | 3A output | Amazon.in |
| Power bank | 20,000 mAh, 3A USB-C | Amazon.in |
| MicroSD card | 64GB, pre-flashed | Amazon.in |
| GPIO LEDs × 3 | Green / Yellow / Red | Any electronics supplier |
| Passive heatsink | RPi 4 compatible | Amazon.in |
| Ruggedized backpack insert | Padded case with ventilation | Custom |

**BOM per unit: ~₹26,544**
All components procurable locally in India. nRF52840 MDK from fabtolab.com (in stock). Rest from Amazon.in.

### Why nRF52840 MDK over CSR8510

| | CSR8510 (rejected) | nRF52840 MDK (selected) |
|---|---|---|
| Type | Dumb radio controlled by Linux kernel | Programmable BLE computer with own ARM CPU |
| Firmware | Fixed, read-only | Custom firmware — runs YOUR attack code on-chip |
| BLE version | 4.0 | 5.0 |
| Radio control | Through Linux BlueZ kernel (gatekeeper) | Direct register access — no gatekeeper |
| Attack speed | 10-15 targets/sec/dongle | 50-100 targets/sec/dongle |
| ADV flood rate | ~1,000 pkt/sec/dongle | ~10,000+ pkt/sec/dongle |
| MAC rotation | Slow (kernel call per change) | Per-packet, instant |
| Malformed packets | Blocked by kernel validation | Full control — can crash target BLE stacks |
| Updatable | No | Yes — flash new firmware = new attack capabilities via AMC |
| Price | ₹350 | ₹2,592 |
| India availability | Flat nano only (no long-range stick available) | In stock at fabtolab.com |

7 nRF52840 > 10 CSR8510. Each dongle 5-7x more capable.

## Software Stack

### Architecture: Two-Layer (RPi coordinator + dongle firmware)

**Layer 1 — Dongle firmware (runs on nRF52840 ARM Cortex-M4F):**
- Custom firmware using nRF SDK or Zephyr RTOS
- Handles all real-time BLE radio operations on-chip
- Connection storm: scan → CONNECT_IND → move on, loop at ~50-100 targets/sec
- ADV flood: blast advertisements at ~10,000 pkt/sec
- Communicates with RPi over USB serial: receives commands, sends telemetry
- Updatable via USB bootloader (new attack vectors via AMC firmware updates)

**Layer 2 — RPi coordinator (Python):**
- `mardak-attack`: asyncio process, sends commands to 7 dongles over USB serial, aggregates telemetry
- `mardak-supervisor`: health monitor, GPIO LED driver, JSON logger to SD card
- systemd auto-start on boot — zero operator interaction

### Framework: Bumble (Google) + nRF SDK
- Bumble for dongle communication from RPi (USB HCI transport)
- nRF SDK / Zephyr for custom dongle firmware
- Hot paths run on dongle ARM CPU, not RPi — RPi is coordinator only

### Field Unit Software
- Raspberry Pi OS Lite (headless)
- systemd auto-start on boot — zero operator interaction
- Dual attack daemon: connection storm (5 dongles) + ADV flood (2 dongles)
- GPIO LED driver: green=running, yellow=degraded, red=error
- Structured JSON logs to SD card (post-op analysis)
- Fully autonomous — no network dependency

### Command Station Software (MARDAK C1)
- Post-op analysis tool (Python)
- Batch SD card import + aggregation
- Dongle firmware update utility
- After-action report generation:
  - Heatmap of device density
  - Timeline of mesh activity before/during/after
  - Estimated disruption percentage
  - Unit performance comparison

## Deployment Topology (1 km² site)

- **8× perimeter units** at 400m spacing — creates outer dead zone
- **4× mobile units** in crowd density zones — fragments internal mesh
- **2× reserve units** — battery swap / crowd movement response
- **1× command vehicle** (200m back) — post-op analysis only (Phase 1)
- **15 total personnel** (plainclothes)

### C2 (Command & Control)
- **Phase 1:** Fully autonomous. No C2 link. Post-op SD card collection.
- **Phase 2:** LoRa telemetry (868MHz) — heartbeat every 30s, remote START/STOP/INTENSITY.

## Operator Interface

### Field Operator (zero tech skill required)
1. Charge power bank
2. Plug power bank into backpack unit
3. Wait for green LED
4. Walk to assigned position
5. At end of operation: power off, return backpack

### Command Operator (trained, 1-2 people)
1. After operation: collect SD cards from all units
2. Batch import into command station
3. Run analysis script
4. Generate after-action report
5. (Optional) Flash dongle firmware updates for next deployment

### Safety Rule
**NO BLUETOOTH DEVICES on personnel within 50m of active MARDAK unit.** Wired earpieces mandatory. Printed on backpack insert label.

## Product SKUs

| SKU | Contents | Price |
|-----|----------|-------|
| **MARDAK F1** | 1× Field Unit, assembled and tested | ₹2,50,000 - 3,00,000 |
| **MARDAK C1** | 1× Command Station (ruggedized laptop + software + firmware utility) | ₹6,00,000 - 8,00,000 |
| **MARDAK D15** | 12+3 reserve F1 + 1× C1 + 15× wired earpieces + 2-day training | ₹50-60 lakh |
| **MARDAK D30** | 25+5 reserve F1 + 1× C1 + 30× wired earpieces + 2-day training | ₹85-100 lakh |

### Pricing Model
- Hardware BOM: ~₹26,544 per unit
- Sell price: 10-15x markup (standard for defence/LEA integrated systems)
- Software IP, custom firmware, integration, testing, training, support = the value
- "Nordic Semiconductor nRF52840" in procurement docs = credibility with defence buyers

### Recurring Revenue
| Service | Price | Cadence |
|---------|-------|---------|
| AMC | 15-18% of kit value | Annual |
| Software + firmware updates (new attack vectors) | Included in AMC | Quarterly |
| On-site training | ₹3-5 lakh per batch | Per engagement |
| Post-op analysis service | ₹1-2 lakh | Per operation |

**5-year LTV per customer: ₹90-110 lakh**

### TAM
28 states + 8 UTs + central agencies (NIA, NSG, CRPF, BSF, state police forces)

## Roadmap

| Phase | Version | Capability | Timeline |
|-------|---------|-----------|----------|
| **1 — MVP** | v1.0 | Autonomous nRF52840 units (connection storm + ADV flood) + post-op analysis | Ship-ready |
| **2 — C2** | v1.5 | LoRa telemetry + real-time command dashboard | +2-3 months |
| **3 — Advanced** | v2.0 | App-specific Sybil attacks + selective jamming + Wi-Fi Direct deauth + malformed packet injection | +4-5 months |
| **4 — Intel** | v3.0 | Passive BLE collection + device fingerprinting + Anveshak integration | +6-8 months |
| **5 — RF Jam** | v4.0 | Integrated RF jamming module (DRDO/DoT partnership) | +12 months |

## Testing Plan

| Level | Setup | Duration |
|-------|-------|----------|
| Lab bench | 1× unit + 20 phones in office | 1 week |
| Controlled outdoor | 5× units + 50 phones, 500m area | 1 week |
| Red/blue team | Blue: 20 people passing messages. Red: 3× MARDAK units. Video recorded. | 1 day |
| Stress test | 1× unit, 8 hours continuous | 1 day |
| Buyer demo | 10 phones on table. MARDAK on → mesh dies <30s. Off → recovers ~60s. | 30 min |

**Target metric:** "MARDAK D15 reduced Bridgefy mesh message delivery from 94% to below 3% across 1 km² within 120 seconds."

## Risk Register

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|------------|
| 1 | BLE 5.x tightens supervision timeout | Medium | High | nRF52840 custom firmware can send partial handshake packets to extend lock. ADV flood as fallback |
| 2 | Mesh app adds flood detection | Medium | Medium | App-specific Sybil modules in Phase 3. Connection storm works below app layer |
| 3 | Thermal throttle (45°C ambient) | High | Medium | Passive heatsink + ventilated backpack insert. nRF52840 runs attack on-chip — RPi load is light |
| 4 | Dongle failure under sustained use | Medium | Low | 7 dongles per unit, losing 1-2 still effective. Spare dongles in command vehicle |
| 5 | Protesters switch to Wi-Fi Direct | Low | High | Phase 3: Wi-Fi Deauth module (same RPi hardware) |
| 6 | Friendly fire on LEA BLE devices | High | Medium | Wired earpieces in kit. Training. Backpack label warning |
| 7 | PR/media risk | Medium | High | LEA's responsibility. We provide technical brief (non-harmful, temporary, no data accessed) |
| 8 | nRF52840 firmware development complexity | Medium | Medium | nRF SDK well-documented. Bumble has nRF52840 examples. Zephyr RTOS as alternative |

## Legal Framework (LEA's Responsibility)

- Indian Telegraph Act S.5(2) — blocking communication in public emergency
- IT Act S.69A — blocking access to computer resources
- Wireless Telegraphy Act S.4 — LEA exemption for government agencies
- CrPC S.144 / BNSS S.163 — magistrate's order for protest site
- Authorization chain: DM order → SP deployment order → DoT standing authorization → written ROE
- SD card logs = legal evidence of authorized usage window
