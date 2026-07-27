# MARDAK — Hardware Validation Plan

## Shopping List

### Phase A: Dev Kit (order now — ₹15,475)

| # | Component | Spec | Qty | Source | Est. Cost |
|---|-----------|------|-----|--------|-----------|
| 1 | Raspberry Pi 4 Model B | 4GB RAM | 1 | Amazon.in / Robu.in | ₹4,500 |
| 2 | nRF52840 MDK USB Dongle | Nordic nRF52840, BLE 5.0, ARM Cortex-M4F, 256KB RAM, 1MB Flash, USB bootloader | 3 | fabtolab.com | ₹7,775 |
| 3 | USB power meter | Inline USB-C/A, voltage + current | 1 | Amazon.in | ₹500 |
| 4 | Power bank | 20,000 mAh, USB-C 3A output | 1 | Amazon.in | ₹2,000 |
| 5 | MicroSD card | 64GB, Class 10 / A2 | 1 | Amazon.in | ₹500 |
| 6 | Passive heatsink | RPi 4 aluminium, adhesive | 1 | Amazon.in | ₹200 |
| **Total** | | | | | **~₹15,475** |

No USB hub needed — RPi 4 has 4 USB ports. 3 dongles plug directly.

### Phase B: Full Unit Test (order after software validated — ₹11,266)

| # | Component | Spec | Qty | Source | Est. Cost |
|---|-----------|------|-----|--------|-----------|
| 1 | nRF52840 MDK USB Dongle | Additional dongles to reach 7 total | 4 | fabtolab.com | ₹10,366 |
| 2 | Powered USB hub | 7-port, 3A+, external power adapter | 1 | Amazon.in | ₹900 |
| **Total** | | | | | **~₹11,266** |

### Phase C: Production (order after full unit validated)
Bulk order for D15/D30 kits. Pricing negotiation with fabtolab.com for volume.

### Scaling Path
1. Dev kit (3 dongles) → validate firmware + software → ₹15,475
2. Full unit (7 dongles) → validate coverage + performance → +₹11,266
3. Production kits → bulk pricing

### Procurement Sources

- **nRF52840 MDK USB Dongle:** https://www.fabtolab.com/maker-dairy-nrf52840-mdk-usb-dongle-form-factor-multiprotocol-soc-network-co-processor-ncp — ₹2,591.58 each, in stock
- **Everything else:** Amazon.in, standard components

### Why nRF52840 MDK (not CSR8510)

CSR8510 long-range stick dongles not available in India. nRF52840 MDK available at fabtolab.com.
nRF52840 is a massive upgrade over CSR8510:

- **CSR8510** = dumb Bluetooth radio controlled by Linux kernel. Fixed firmware. 10-15 targets/sec. ~1000 ADV flood pkt/sec. BLE 4.0 only.
- **nRF52840** = programmable BLE computer with own ARM Cortex-M4F CPU. Custom firmware runs attack logic on-chip. 50-100 targets/sec. ~10,000+ ADV flood pkt/sec. BLE 5.0. Updatable.

7 nRF52840 dongles > 10 CSR8510 dongles. Each dongle 5-7x more capable.

## Validation Tests (run in order)

### HW-1: Dongle Enumeration
**Question:** Do 3× nRF52840 MDK enumerate as separate USB serial/HCI devices on RPi 4 USB ports?
**Method:** Plug 3 dongles directly into RPi 4 USB ports → `lsusb` and `ls /dev/ttyACM*`
**Pass:** All 3 show as separate devices (ttyACM0-ttyACM2 or hci0-hci2 depending on firmware mode)
**Fail fallback:** Check USB power — try powered hub if brownout suspected.
**Note:** nRF52840 MDK ships with OpenThread NCP firmware. May appear as USB CDC ACM serial device, not HCI. Need to flash BLE HCI firmware or custom attack firmware first.
**Scale-up check:** 7-dongle enumeration tested in Phase B with USB hub.

### HW-1b: Firmware Flashing
**Question:** Can we flash custom firmware to dongles via USB bootloader?
**Method:** Hold dongle button → plug in → appears as USB mass storage → drag .hex file → auto-reboot
**Pass:** All 3 dongles accept firmware, reboot, appear with new identity
**Fail fallback:** Use nRFUtil command-line tool or J-Link programmer

### HW-2: Power Draw
**Question:** Does total power draw stay within power bank capacity?
**Method:** USB power meter between power bank and RPi. Measure at idle, then 3 dongles active.
**Pass:** Total < 2.5A (power bank 3A output minus safety margin)
**Note:** nRF52840 draws ~15mA active (vs CSR8510 ~50mA). 3 dongles = ~45mA. Extrapolate: 7 dongles = ~105mA.
**Fail fallback:** Very unlikely — nRF52840 is ultra-low-power by design.

### HW-3: Concurrent BLE Operations
**Question:** Can 3 dongles do simultaneous BLE scan + connect operations?
**Method:** Flash basic BLE scanner firmware on all 3. Start scan on all simultaneously. Verify all return results.
**Pass:** All 3 return scan results independently within 200ms.
**Fail fallback:** USB contention — test with powered hub.
**Scale-up check:** 7-dongle concurrency tested in Phase B.

### HW-4: Thermal (2-hour stress test)
**Question:** Does RPi stay below thermal throttle under sustained load?
**Method:** Run 3 dongles at max rate for 2 hours. Monitor `vcgencmd measure_temp`.
**Pass:** CPU temp stays < 75°C (throttle at 80°C).
**Note:** RPi load much lighter with nRF52840 — attack logic runs on dongle CPU, not RPi. RPi just sends commands and logs telemetry. 3 dongles = lighter than 7, but RPi load is coordinator-only regardless.
**Fail fallback:** Add active fan (₹150) or reduce duty cycle.

### HW-5: Battery Life
**Question:** How long does 20Ah power bank sustain full attack load?
**Method:** Full attack load until power bank dies. Log timestamp at start and shutdown.
**Pass:** ≥ 4 hours.
**Note:** Lower total power draw than CSR8510 plan — expect 5-6 hours.
**Fail fallback:** Very unlikely to fail.

### HW-6: Supervision Timeout Measurement
**Question:** What is the actual BLE supervision timeout on real phones?
**Method:** Flash connection storm firmware on 1 dongle. Send CONNECT_IND to test phone. Measure time until phone resumes advertising. Use second dongle as sniffer to detect when target resumes advertising.
**Test phones:** 2-3 Android (different vendors/versions), 1 iPhone.
**Purpose:** Determines final dongle allocation (Phase B) — if 6s timeout, 5 storm + 2 flood. If 2-3s, may need more storm dongles.

### HW-7: nRF52840 Raw Radio Capability
**Question:** Can we achieve ~10,000 ADV packets/sec from one dongle with custom firmware?
**Method:** Flash ADV flood test firmware (bare-metal nRF SDK, direct radio peripheral access). Count packets sent per second. Use second dongle as BLE sniffer to verify.
**Pass:** ≥ 5,000 pkt/sec per dongle.
**Fail fallback:** If limited by BLE spec timing, use selective jamming (carrier wave) instead of packet flooding.
**Note:** 3 dongles perfect for this — 1 floods, 1 sniffs, 1 spare.

## Continuation Prompt (for next session after hardware arrives)

```
/onboard

MARDAK dev kit arrived. Continuing from docs/mardak_product_spec.md and docs/mardak_hw_validation_plan.md

We were in a /grill-with-docs session on Phase 1 software architecture.
Hardware grilling is done — decisions locked in those docs.

Components received (Phase A dev kit):
- RPi 4 (4GB) × 1
- nRF52840 MDK USB Dongle × 3 (from fabtolab.com)
- Power bank × 1
- USB power meter × 1

Ready to run HW-1 through HW-7 validation tests with 3 dongles.
Write the test scripts/firmware and walk me through running them.

HW-1: Do 3 dongles enumerate on RPi 4 USB ports?
HW-1b: Can we flash custom firmware via USB bootloader?
HW-2: Power draw measurement (extrapolate to 7)
HW-3: 3 concurrent BLE operations
HW-4: Thermal under sustained load (2hr)
HW-5: Battery life (full drain)
HW-6: Supervision timeout measurement on real phones (1 attack + 1 sniffer)
HW-7: Raw ADV flood rate test (1 flood + 1 sniffer)
```

## Decisions Locked (from grilling session)

- Attack method: BDoS-first (connection storm + ADV flood), RF jam escalation only
- App-agnostic: attacks BLE protocol layer, not app-specific
- Hardware: RPi 4 (4GB) + nRF52840 MDK USB Dongles (from fabtolab.com, in stock in India)
- Dev kit: 3 dongles (₹15,475). Full unit test: +4 dongles + USB hub (₹11,266). Production: bulk order.
- Production dongles: 7 per unit (5 storm + 2 flood). nRF52840 is 5-7x more capable per dongle than CSR8510
- Antenna: integrated 2.4GHz chip antenna on nRF52840 MDK (~30-50m range)
- Software: two-layer — custom nRF SDK firmware on dongles + Python coordinator on RPi
- Two-process on RPi: mardak-attack (dongle coordinator) + mardak-supervisor (LED + logger)
- Deployment: 15 units (8 perimeter + 4 mobile + 2 reserve + 1 command vehicle)
- C2: Phase 1 autonomous only, LoRa in Phase 2
- Operator interface: 3 GPIO LEDs, turnkey auto-start, zero tech skill required
- Product model: Anduril-style kit product, 10-15x markup
- Product name: MARDAK (मर्दक — Suppressor)
- Procurement: nRF52840 from fabtolab.com, rest from Amazon.in
- Post-op: SD card JSON logs + command station analysis tool
- Firmware updates: new attack vectors delivered as dongle firmware via AMC
