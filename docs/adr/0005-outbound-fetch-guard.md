# ADR 0005: The outbound fetch path validates every hop, not the first

- Status: Accepted
- Date: 2026-09-11
- Issue: #55, follow-up to #43

## Context

Scraped content chooses the addresses the scraper fetches.
A link in a feed, a link in a page and a media URL in markup are all written by whoever we are collecting from, and each becomes an outbound request from a worker that sits on the internal network alongside postgres, redis, ollama and the API.

Before this change the destination was judged once, before the request.
`validate_external_url` read the URL as written, and `validate_external_url_resolved`, added in #43, resolved the hostname and refused an answer inside the deployment.
Three paths got past that.

Redirects.
`fetch_html` and the trafilatura fallback both followed redirects, so the host that was finally fetched was not the host that was validated.

The browser.
`fetch_article` drives Crawl4AI and Playwright, which resolve and navigate on their own, under no address check.

Rebinding.
The address was resolved during validation and again by the client that connected, so a name whose answer changed between the two was validated on one address and fetched on another.

The consequence in each case is the same: a request judged external is issued against an address that is not, and whatever answers is extracted and written into `content_items` as collected intelligence.

## Decision

Validation is a property of the fetch path rather than a call each caller has to remember.

1. One shared path, `sdk/anveshak/net/safe_fetch.py`, carries every outbound fetch of an untrusted address: web, RSS, dark web, PDF, media, scraper health checks and the source registration probes in the API.
   It lives in the SDK because the media downloader is there, and it is one of the paths.
   The API probes are included because discovery registers addresses it read out of scraped markup, and that probe leaves the process holding the database credentials.
2. Redirects are never followed by the client.
   `safe_fetch` walks the chain itself, running the guard on every hop, bounded by `SCRAPER_MAX_REDIRECTS`.
   A hop into the deployment is refused before the request is made rather than after the body is read.
3. The connection is made to the address the guard resolved.
   The address goes in the URL, the name goes in the `Host` header, and the name goes in the TLS `sni_hostname` extension in its ASCII form, so the certificate is still verified against the name.
   A name resolved once cannot answer differently the second time, because there is no second time.
   Every address the resolver returned is carried, not only the first, so a multi-homed host with one unreachable address is a retry rather than a failed fetch.
   Connection reuse is off on that path: a pooled connection is keyed on the pinned address, and reusing one across a redirect to a second name sharing that address would send the second `Host` down a connection whose certificate was checked against the first.
4. Each caller may extend the guard rather than replace it.
   The archive backfill hangs its length bound, per-domain gap and robots.txt check off the same call, so every hop pays them and not only the first.
5. A proxied fetch does not pin an address, whatever its guard returned.
   Tor resolves `.onion` names on its side, and resolving one here is the DNS leak the dark web path exists to avoid, so the written-form check plus the `.onion` rule is what applies and the degradation is logged once per process.
6. The browser is guarded at the page, not at the client.
   Crawl4AI is given a Playwright route handler that runs the same guard over every request the page makes, with one verdict per host rather than one per asset.
   The page is also stopped from registering a service worker, whose requests bypass route interception entirely, and WebSockets are routed through the same guard where the Playwright build can intercept them.
   The top-level URL is validated before navigation as well, because the route guard is conditional on a setting, on this Crawl4AI build exposing a hook, and on the route attaching.
   It can be turned off with `SCRAPER_BROWSER_ADDRESS_GUARD` where a deployment relies on egress policy instead, and says so in the log when it is off or could not be installed.
7. Egress policy is the control that covers what the process cannot.
   In k3s the collectors may reach `0.0.0.0/0` on ports 80 and 443 with the private ranges excluded, and reach postgres, redis and ollama by pod selector instead.
   DNS egress is scoped to the cluster resolver rather than to every destination, because port 53 to the internet is an exfiltration path out of the pod this policy set otherwise fences in.
   A refusal is never an exception: the fetch path returns a `FetchFailure` carrying the reason, which is what `sources.health_error` shows an analyst, and a guard that raises is treated as a refusal rather than propagated.

## Consequences

A redirect into the deployment is refused, a rebound name is never fetched, and the browser's own requests are judged.
The in-process checks narrow rather than close: Chromium resolves the name again when it connects, so the browser path still has the window that pinning closes for httpx, and a Playwright build without WebSocket interception leaves that one open.
Egress policy is what closes it, which is why the k3s policy is part of this change rather than a follow-up.

Compose has no egress policy.
A Compose deployment therefore relies on the in-process guards alone, and the browser window stays open there.
That is stated here rather than left to be discovered: the deployment that needs the guarantee is the k3s one, and a Compose deployment handling real collection should place the scraper behind a network its internal services do not share.

Every path pays a DNS lookup per hop it did not pay before, which is a round trip against a resolver that has usually just answered the same question.
A fetch that was a single call is now a walk, so a site answering with a chain of five redirects costs five validations, which is the point rather than an overhead to remove.
