---
name: passlib-bcrypt-incompatibility
description: passlib 1.7 breaks with bcrypt>=4.0 — replace with direct bcrypt wrapper
type: feedback
---

`passlib 1.7.x` + `bcrypt>=4.0.0` is broken. bcrypt 4.0 removed `__about__` and changed its
internal API. passlib's `detect_wrap_bug()` calls bcrypt with a >72-byte test secret which
bcrypt 4.x rejects with `ValueError: password cannot be longer than 72 bytes`.

**Symptom:** `CryptContext(schemes=["bcrypt"])` raises ValueError on first use — even before
any real password is hashed. All login endpoints return HTTP 500.

**Fix:** replace passlib entirely with a thin direct-bcrypt wrapper:

```python
import bcrypt as _bcrypt

class _BcryptContext:
    """Direct bcrypt wrapper — avoids passlib 1.7 / bcrypt>=4 incompatibility."""

    def verify(self, secret: str, hashed: str) -> bool:
        return _bcrypt.checkpw(secret.encode(), hashed.encode())

    def hash(self, secret: str) -> str:
        return _bcrypt.hashpw(secret.encode(), _bcrypt.gensalt(rounds=12)).decode()

pwd_context = _BcryptContext()
```

Drop the `passlib` import and `CryptContext` entirely. The wrapper is a drop-in replacement
for the two methods used in auth code (`verify`, `hash`).

**Why:** passlib is effectively unmaintained and incompatible with modern bcrypt. Using bcrypt
directly is simpler and future-proof.

**How to apply:** any time `passlib.context.CryptContext` appears in a Python service — swap
immediately. Also regenerate any stored password hashes if they were created with the old
passlib bcrypt backend (they may be invalid).
