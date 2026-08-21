# httpx SOCKS Proxy Requires Optional Extra

## When this applies
Any service that uses httpx through a SOCKS5 proxy (Tor, SSH tunnels, etc.).

## The pitfall
`httpx>=0.27` installs httpx but NOT the SOCKS transport. When code hits a
`socks5://` proxy URL, it fails at runtime:

```
Using SOCKS proxy, but the 'socksio' package is not installed.
Make sure to install httpx using `pip install httpx[socks]`.
```

This only surfaces in containers where Crawl4AI (primary path) fails and
the trafilatura fallback (httpx) tries the SOCKS proxy.

**How we lost time:** Unit tests mock HTTP so they never exercise the SOCKS
path. The bug only appeared when running `make test-scrape` against real
.onion sites inside the scraper container.

## The fix
In `pyproject.toml`:
```toml
# WRONG — no SOCKS support
"httpx>=0.27",

# RIGHT — includes socksio for SOCKS5 proxy
"httpx[socks]>=0.27",
```

## General rule
When a Python package has optional extras (`[socks]`, `[async]`, `[all]`),
and you use that feature path, always declare the extra in pyproject.toml.
Don't rely on it being pulled in transitively.

## Hot-patching containers (temporary)
```bash
docker exec -u root anveshak-scraper-1 pip install socksio
```
This is ephemeral — lost on container restart. The permanent fix is the
pyproject.toml change + `make build`.
