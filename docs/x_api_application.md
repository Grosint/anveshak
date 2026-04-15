# X / Twitter API Application — Use Case Description

Use this text when applying for X API access at developer.x.com.

---

## Application: Pay-Per-Use Access (Basic tier)

**Steps:**
1. Create an X developer account at developer.x.com
2. Sign up → fill the use case form using the text below
3. Instant approval for pay-per-use Basic access
4. Set `X_BEARER_TOKEN` in your `.env` file
5. Set `X_ADAPTER_ENABLED=true`
6. Set `X_MONTHLY_READ_CAP` to your budget (e.g. 40000 = ~$200/month at $0.005/read)

---

## Use Case Description (copy-paste into X developer form)

**Describe all of your use cases of X's data and API:**

> Anveshak is a sovereign AI-OSINT (Open Source Intelligence) analysis and monitoring platform used by defence and security analysts to monitor publicly available information relevant to national security topics.
>
> Our specific use cases for the X API are:
>
> **1. Topic-based monitoring**: We use the recent search endpoint (GET /2/tweets/search/recent) to collect publicly posted tweets matching analyst-defined keyword sets (e.g. specific geopolitical topics, equipment names, location references). We poll every 15 minutes per topic within the 7-day recency window. We do NOT collect personal user data — we collect public topical content only.
>
> **2. Narrative cluster detection**: Retrieved tweets are fed into an on-premises NLP pipeline to identify emerging narrative clusters around monitored topics. This is fully automated analysis with no human review of individual posts — analysts see only aggregated cluster labels and trend summaries.
>
> **3. Disinformation signal detection**: We use tweet metadata (account age, follower ratios, coordination patterns) as one signal in a multi-source credibility scoring system. We do NOT store user PII beyond the tweet ID and public handle required for citation.
>
> **4. Evidence documentation**: For significant items, we archive the public tweet URL and tweet ID as a reference citation in analyst reports. We store only the tweet text, ID, author handle, and timestamp — no DMs, no account PII beyond public metadata.
>
> **Data handling**: All data is processed on-premises. No data is shared with third parties. Data is used solely for the intelligence monitoring described above. Retention is 90 days for tweet content, indefinite for report citations.
>
> **Volume**: We operate within the Basic tier limits. Estimated monthly reads: 20,000–40,000 depending on active topic count. We enforce a hard budget cap (`X_MONTHLY_READ_CAP`) that halts all API calls when the monthly read limit is reached.
>
> We do not intend to: build a consumer product, enable third-party access to X data, create a competing service, or display tweets outside of our secure analyst workbench environment.

---

## What NOT to put in the form

- Do not mention "scraping" — this is an official API integration
- Do not mention competitor intelligence — frame as open-source monitoring
- Do not mention specific countries or adversaries — keep it generic

---

## After approval

1. Create a project in the developer portal
2. Generate a Bearer Token (for read-only search)
3. Add to `.env`:
   ```
   X_BEARER_TOKEN=AAAAAAAAAAAAAAAAAAAAAAxxxx...
   X_ADAPTER_ENABLED=true
   X_MONTHLY_READ_CAP=40000
   ```
4. Verify it works: `make health` → social service health endpoint shows X adapter active

---

## Cost reference (pay-per-use Basic tier as of 2025)

| Operation | Cost |
|-----------|------|
| Read (search/timeline) | $0.005 per read |
| Write | $0.005 per write |
| 40,000 reads/month | ~$200/month |
| 8,000 reads/month | ~$40/month |

The `X_MONTHLY_READ_CAP` guard in `social/settings.py` enforces a hard stop.
The social service will log a warning and skip X polling once the cap is reached for the month.

---

## Upgrade path: Enterprise (Filtered Stream)

For real-time push (no polling) and full-archive search (back to 2006),
an Enterprise API contract with X Corp is required.

Cost: negotiate with X Corp post-award (~$42,000+/month at scale).

To activate when contract is in place:
```
X_ADAPTER_MODE=stream          # was: polling
X_MONTHLY_READ_CAP=unlimited
X_BEARER_TOKEN=<enterprise token>
```

No code changes required — `XPollingAdapter` and `XStreamAdapter` both implement
`SourceAdapterBase`. Social service loads by `settings.x_adapter_mode`.
See `hardware.md` for full upgrade matrix.
