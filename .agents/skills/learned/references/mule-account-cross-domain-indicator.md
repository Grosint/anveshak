# Mule Accounts Are Cross-Domain Criminal Infrastructure

## Pattern
Mule account recruitment on social media is shared infrastructure for BOTH
cyber fraud AND narcotics. Same Telegram channels, same recruitment language,
same identifier patterns (phone + UPI + bank account).

Same Engine C identifier extraction catches both:
- Cyber fraud: mule accounts launder investment scam / digital arrest proceeds
- Narco: mule accounts launder drug sale proceeds
- Often the SAME mule network serves both ecosystems

## When to apply
- When building fraud detection features — don't silo cyber vs narco
- When designing scam templates — mule_recruitment applies to both categories
- When cross-topic convergence fires between cyber fraud and narco topics = shared infrastructure

## Source
CCITR Karnataka CID report (2025):
- 4,000 mule accounts reported daily to CFCFRMS
- Investment fraud = 70.5% of cybercrime losses in Bengaluru (₹468 Cr in 2024)
- "In most cases, fraudsters opt to use Mule Account as a Service"
- Recruitment via Telegram, WhatsApp, Facebook, Instagram
- Keywords used by criminals: "bank accounts", "corporate accounts", "account business",
  "renting account", "gaming funds" (from page 17 of report)
- Complicit mules "advertise their services online or recruit other money mules"
- Integration stage: cryptocurrency (primarily USDT), cash withdrawal, hawala

## Key identifiers to extract
Phone (Indian), UPI ID, Telegram handle, GSTIN (shell company facade),
Udyam registration (small business facade), crypto wallet (BTC/ETH/TRC-20)
