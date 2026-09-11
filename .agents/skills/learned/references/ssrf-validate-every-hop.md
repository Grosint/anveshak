# SSRF: Validate Every Hop, Connect to the Address You Judged

## When to load: writing or reviewing any fetch of a URL that scraped content chose

---

## Rule 1: One check before the request is not a check

Three things get past a validate-then-fetch pair:

1. **Redirects.** `follow_redirects=True` hands the choice of final host to whoever
   wrote the link. A validated public URL 302s to `http://ollama:11434/` and the
   body of an internal service is extracted as collected intelligence.
2. **Rebinding.** The guard resolves the name, then the client resolves it again.
   An attacker who controls the zone chooses the second answer.
3. **The browser.** Crawl4AI and Playwright resolve and navigate inside their own
   process. The httpx-side guard never sees those requests at all.

## Rule 2: Build the fetch path, not another helper

Put the walk in one module (`sdk/anveshak/net/safe_fetch.py`) and make every
untrusted fetch go through it: web, RSS, dark web, PDF, media, health probes.
A guard each caller has to remember is a guard a new caller will not.

```python
result = await fetch_bytes(url, timeout=30, guard=my_guard, limit=_MAX_BYTES)
```

The client is built with `follow_redirects=False` and the chain is walked here,
running the guard on every hop, bounded by a setting.

## Rule 3: Pin the address the guard approved

```python
parsed = httpx.URL(url)
client.build_request(
    "GET",
    parsed.copy_with(host=target.address),          # no second lookup
    headers={"Host": parsed.netloc.decode("ascii")},  # site still serves the right host
    extensions={"sni_hostname": parsed.host},         # TLS still verified against the name
)
```

`sni_hostname` is what keeps certificate verification honest when the URL carries
an IP. Without it the cert is checked against the address and every HTTPS fetch fails.

## Rule 4: A proxied fetch pins nothing

Tor resolves `.onion` on its side. Resolving it here is the DNS leak the dark web
path exists to avoid. Use a written-form guard, return no address, and log the
degradation once per process rather than once per request.

## Rule 5: The browser is guarded at the page

```python
strategy.set_hook("on_page_context_created", hook)  # hook calls context.route("**/*", handler)
```

Route every request through the same guard, cache one verdict per host (a page of
assets must not be a page of DNS lookups), and let inert schemes (`data:`, `blob:`,
`about:`) through since they issue no request. Log when the hook could not be
installed: the deployment is then relying on egress policy alone.

## Rule 6: Egress policy is the only control that covers the browser

k3s: allow the collectors `0.0.0.0/0` on 80/443 with the private ranges in
`except`, and grant postgres/redis/ollama by pod selector instead. Compose has no
equivalent, so a Compose deployment keeps the browser window open — say so rather
than implying coverage.

A NetworkPolicy whose selector matches no pod applies to nothing, silently. Test
that every policy's `app` values exist as deployment labels.

## Checklist (any new outbound fetch)

- [ ] Goes through `safe_fetch`, not a fresh `httpx.AsyncClient`
- [ ] Byte bound passed, measured after decompression
- [ ] Caller's own checks (rate limit, robots.txt) inside the guard, so every hop pays them
- [ ] Test: a redirect into the deployment is refused and never requested
- [ ] Contract test still passes: no `follow_redirects=True` under the untrusted roots

See: `docs/adr/0005-outbound-fetch-guard.md`, `tests/unit/test_safe_fetch.py`
