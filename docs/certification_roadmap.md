# Anveshak — Certification Roadmap
## Garud Research & Tech Private Limited

**Created:** 2026-04-17
**Purpose:** Track certification strategy for defence credibility and government procurement readiness

---

## Priority Matrix

| Priority | Certification | Impact on Defence Sales | Timeline | Status |
|----------|--------------|------------------------|----------|--------|
| P0 | ISO 27001:2022 | Mandatory for most defence/govt RFPs | M1-M3 | NOT STARTED |
| P0 | STQC Certification | MeitY stamp, preferential govt procurement | M1-M3 | NOT STARTED |
| P1 | MeitY Empanelment | Approved vendor list for govt IT | M1-M4 | NOT STARTED |
| P2 | SOC 2 Type II | International SaaS security standard | Post-programme | NOT STARTED |
| P2 | ISO 9001:2015 | Quality management (bundle with 27001 renewal) | Post-programme | NOT STARTED |
| P3 | DRDO/CAIR Security Evaluation | Defence-specific endorsement | Post-programme | NOT STARTED |
| P3 | NCIIPC Compliance | Critical infrastructure protection | Post-programme | NOT STARTED |
| P4 | Common Criteria EAL2+ | International defence export readiness | 12-18 months post | NOT STARTED |

---

## P0: ISO 27001:2022 — Information Security Management System

### Why This Is Non-Negotiable

ISO 27001 is the single most requested certification in Indian government and defence RFPs. Without it, Anveshak will be disqualified from most tenders before technical evaluation even begins. It covers:

- Information security policies and risk management
- Access control and authentication
- Data handling, storage, and disposal
- Incident response and business continuity
- Supplier and third-party security
- Physical and environmental security

### What Needs to Be Done

**Phase 1: Gap Assessment (Week 1-2)**
- Hire an ISO 27001 consultant or certification body (e.g., BSI, TUV, Bureau Veritas, IRQS)
- Conduct gap assessment against ISO 27001:2022 Annex A controls
- Identify what Anveshak already satisfies vs what needs to be implemented

**Phase 2: ISMS Implementation (Week 3-8)**
- Define Information Security Management System (ISMS) scope — cover both GrosINT SaaS and Anveshak on-premise deployment
- Document required policies:
  - Information Security Policy
  - Access Control Policy
  - Data Classification Policy (critical for defence — classify content_items, reports, source data)
  - Incident Response Plan
  - Business Continuity Plan
  - Acceptable Use Policy
  - Cryptographic Controls Policy
  - Supplier Security Policy
- Implement controls:
  - Formal access control procedures (already have JWT auth, rate limiting)
  - Audit logging (already have credibility_audit_log, structured logging)
  - Encryption at rest and in transit (need to verify PostgreSQL TLS, Redis TLS)
  - Backup and recovery procedures (already have make backup/restore)
  - Vulnerability management process
- Train both founders on ISMS responsibilities
- Conduct internal audit

**Phase 3: Certification Audit (Week 9-12)**
- Stage 1 Audit: Documentation review — certification body reviews ISMS documentation
- Stage 2 Audit: Implementation audit — auditor verifies controls are operational
- Address any non-conformities
- Receive ISO 27001:2022 certificate

### Anveshak's Current Strengths (Already Implemented)

| ISO 27001 Control Area | Anveshak Status | Evidence |
|------------------------|----------------|----------|
| A.8 — Access Control | JWT auth on all endpoints, rate limiting | Phase 8 criteria 8.1, 8.2 |
| A.8 — Logging & Monitoring | structlog JSON, Prometheus, Grafana, Loki | Phase 8 criteria 8.7-8.11 |
| A.8 — Data Classification | Labels on every Pydantic model, content_hash logging only | Architectural rules 2, AGENTS.md security rules |
| A.8 — Cryptographic Controls | bcrypt password hashing, JWT tokens | Phase 8 criterion 8.1 |
| A.8 — Backup | pg_dump + Redis RDB + media archive via Makefile | make backup/restore |
| A.8 — Secure Development | Bandit scan zero HIGH, no hardcoded secrets, Pydantic strict mode | Phase 8 criteria 8.5, 8.6 |
| A.8 — Supplier Management | No cloud LLM, sovereign deployment | Architectural rule 10 |

### Gaps to Address

| Gap | What's Needed | Effort |
|-----|--------------|--------|
| Formal ISMS documentation | Written policies (templates available from consultant) | Medium — mostly documentation |
| PostgreSQL TLS | Verify/enable TLS for DB connections | Low |
| Redis TLS | Enable TLS for Redis connections | Low |
| Encryption at rest | Enable PostgreSQL data-at-rest encryption or LUKS on volume | Medium |
| Formal incident response plan | Document IR procedures, contact chains, escalation | Low — documentation |
| Vulnerability management process | Regular dependency scanning (safety, pip-audit), CVE tracking | Low — tooling exists |
| Management review process | Quarterly ISMS review meetings (just the 2 founders initially) | Low |
| Risk assessment register | Formal risk register with likelihood/impact scoring | Medium — documentation |

### Cost Estimate

| Item | Cost |
|------|------|
| Certification body (Stage 1 + Stage 2 audit) | 1.5-2.5L |
| Consultant for gap assessment + implementation support | 1-2L |
| Annual surveillance audit (year 2+) | 0.75-1L/year |
| **Total Year 1** | **3-5L** |

### Recommended Certification Bodies (India)

- BSI Group India
- TUV SUD South Asia
- Bureau Veritas India
- IRQS (Indian Register Quality Systems)
- DNV India

---

## P0: STQC Certification — MeitY Software Testing

### Why This Matters

STQC (Standardisation Testing and Quality Certification) is under MeitY (Ministry of Electronics & Information Technology). STQC-certified products receive preferential consideration in government procurement. For defence software, this is a strong trust signal that says "the Indian government's own testing body has validated this product."

### What Needs to Be Done

**Step 1: Apply to STQC (Week 1)**

- Submit application to nearest STQC Directorate (Delhi or regional office)
- Specify testing scope: Anveshak platform (all 5 modules)
- Provide product documentation, user manuals, test reports

**Step 2: STQC Functional Testing (Week 2-6)**
- STQC tests against claimed functionality
- Provide test environment (Docker Compose setup on STQC hardware or cloud instance)
- STQC verifies:
  - Functional correctness of all claimed features
  - Security testing (authentication, authorisation, input validation)
  - Performance testing (response times, throughput)
  - Usability assessment
  - Documentation completeness

**Step 3: Report & Certificate (Week 7-10)**

- STQC issues test report
- Address any findings
- Receive STQC certification

### Preparation Checklist

- [ ] User manual / product documentation (can generate from existing docs/architecture.md + docs/analyst_walkthrough.md)
- [ ] Test environment setup instructions (already have: make up && make init && make seed-demo)
- [ ] Claimed feature list mapped to PS-18 modules
- [ ] Existing test reports (267 unit + 20 e2e test results)
- [ ] Security scan reports (bandit output)

### Cost Estimate

| Item | Cost |
|------|------|
| STQC testing fee | 1.5-3L (depends on scope) |
| Environment preparation | Minimal (already have Docker Compose) |
| Documentation preparation | Internal effort |
| **Total** | **2-4L** |

### STQC Contact

- Website: https://www.stqc.gov.in
- IT Testing: STQC IT Centre, Electronics Niketan, CGO Complex, New Delhi
- Regional labs: Bengaluru, Kolkata, Mumbai, Hyderabad

---

## P1: MeitY Empanelment

### Why This Matters

MeitY empanelment puts Garud Research on the approved vendor list for government IT procurement. When IAF (or any government body) wants to procure Anveshak, having MeitY empanelment simplifies the procurement justification — they're buying from an approved vendor, not an unknown entity.

### What Needs to Be Done

**Step 1: Check Current Empanelment Categories**
- Visit GEM (Government e-Marketplace) portal: https://gem.gov.in
- Register Garud Research as a seller if not already registered
- List Anveshak under relevant product categories (software, AI/ML solutions, cybersecurity tools)

**Step 2: MeitY Cloud / Software Empanelment**
- Apply under relevant MeitY empanelment scheme
- Provide company documentation: DPIIT registration, GST, PAN, incorporation certificate
- Provide product documentation and demo access

**Step 3: GeM Listing**
- List Anveshak on GeM with detailed product specifications
- Set pricing for different deployment tiers
- This enables direct government procurement without tendering for purchases under threshold

### Cost Estimate

| Item | Cost |
|------|------|
| GeM registration | Free |
| MeitY empanelment process | Minimal (administrative) |
| Documentation preparation | Internal effort |
| **Total** | **Minimal — mostly process effort** |

---

## P2: SOC 2 Type II (Post-Programme)

### Why This Matters

SOC 2 Type II is the international gold standard for SaaS security. Since GrosINT operates as SaaS with 300 defence/LE users, SOC 2 covers the existing product AND signals organisational maturity. It's increasingly asked for by sophisticated government buyers and is mandatory for any international defence sales.

### Scope

- Cover GrosINT SaaS operations
- Cover Anveshak deployment support services
- Trust Service Criteria: Security, Availability, Processing Integrity, Confidentiality

### Timeline & Cost

- **Duration:** 6-9 months (3-month readiness + 3-6 month observation period for Type II)
- **Cost:** 5-10L (auditor fees + tooling)
- **Prerequisite:** ISO 27001 makes SOC 2 significantly easier — 60-70% control overlap

---

## P2: ISO 9001:2015 (Post-Programme)

### Why This Matters

Quality management standard. Less impactful than ISO 27001 alone but often listed as a co-requirement in defence RFPs ("ISO 27001 and ISO 9001 certified"). Can be audited simultaneously with ISO 27001 surveillance audit for lower marginal cost.

### Timeline & Cost

- **Duration:** 2-3 months (if done alongside 27001, much of the QMS documentation overlaps)
- **Cost:** 2-3L standalone, ~1-1.5L incremental if bundled with 27001 renewal
- **When:** Bundle with ISO 27001 first surveillance audit (12 months after initial certification)

---

## P3: DRDO / CAIR Security Evaluation (Post-Programme)

### Why This Matters

If DRDO's Centre for Artificial Intelligence and Robotics (CAIR) evaluates Anveshak, it is essentially a defence endorsement. This carries more weight with IAF than any commercial certification. Very hard to get independently, but the iDEX relationship provides a pathway.

### How to Pursue

1. Through iDEX programme manager — request DRDO evaluation as part of PS-18 acceptance
2. Through CAIR directly — submit Anveshak for AI security evaluation
3. Through IAF sponsor — if the IAF wing using Anveshak requests DRDO validation

### What They Would Evaluate

- Data sovereignty guarantees (no data egress)
- LLM security (prompt injection resistance, output validation)
- Authentication and access control
- Deployment security (container hardening, network isolation)
- Code security (static analysis, dependency vulnerabilities)

### Cost: Varies (government process, may be covered under iDEX programme)

---

## P3: NCIIPC Compliance (Post-Programme)

### Why This Matters

If IAF classifies their OSINT infrastructure under National Critical Information Infrastructure Protection Centre (NCIIPC) guidelines, compliance becomes mandatory. Getting ahead of this requirement shows foresight and security maturity.

### What's Involved

- Comply with NCIIPC guidelines for critical information infrastructure
- Implement additional controls for network segmentation, access logging, incident reporting
- Regular vulnerability assessments and penetration testing

### When to Pursue

- Only if IAF designates Anveshak deployment as critical infrastructure
- Worth mentioning in proposals as "NCIIPC-ready architecture"

---

## P4: Common Criteria EAL2+ (Long-Term)

### Why This Matters

Common Criteria is the international mutual recognition standard for IT security evaluation. Used by NATO, Five Eyes, and most defence organisations globally. If Anveshak ever sells to friendly nations or through defence export channels, CC certification is expected.

### Timeline & Cost

- **Duration:** 12-18 months
- **Cost:** 15-25L (evaluation facility + documentation)
- **When:** Only pursue if international defence sales become a realistic target

---

## Budget Summary

### Within 9-Month Programme (Fund from Grant)

| Certification | Cost | Timeline |
|--------------|------|----------|
| ISO 27001:2022 | 3-5L | M1-M3 |
| STQC Certification | 2-4L | M1-M3 |
| MeitY / GeM Empanelment | ~0.5L | M1-M4 |
| **Total** | **5.5-9.5L** | |

### Post-Programme (Fund from Revenue/Next Round)

| Certification | Cost | Timeline |
|--------------|------|----------|
| SOC 2 Type II | 5-10L | 6-9 months |
| ISO 9001:2015 | 1.5-3L | 2-3 months |
| DRDO/CAIR Evaluation | Varies | 6-12 months |
| Common Criteria EAL2+ | 15-25L | 12-18 months |

---

## Action Items — Immediate (This Week)

- [ ] Research ISO 27001 certification bodies — get 3 quotes (BSI, TUV, Bureau Veritas)
- [ ] Register on GeM portal if not already done
- [ ] Contact STQC IT Centre Delhi for application process and timeline
- [ ] Prepare product documentation package (compile from existing docs/)
- [ ] Verify PostgreSQL and Redis TLS configuration in Docker Compose
- [ ] Run pip-audit / safety check on all Python dependencies for known CVEs
