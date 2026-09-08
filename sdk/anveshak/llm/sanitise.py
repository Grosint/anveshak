"""Sanitisation for untrusted text bound for a prompt.

Scraped content is untrusted input. Interpolating it into an instruction
block puts it at the same level as the task, so a post can carry its own
instructions and steer the answer. Pydantic validation on the way out bounds
the shape of the damage; it does nothing about the content of the fields.

Two defences, applied together:

  - Neutralise the sequences that end a delimited block or open a new turn,
    so content cannot escape the fence it is placed in.
  - Fence the content and tell the model the fence is data.

Neither is complete on its own and no sanitiser is complete in general, which
is why every caller also validates the answer through a schema.
"""

from __future__ import annotations

import re

# Sequences that either close a delimiter this module opens, or open a new
# conversational turn in the formats models are trained on.
_INJECTION_MARKERS = re.compile(
    r"""(
        </?\s*untrusted[^>]*>      # the fence this module writes
      | <\|[^|>]*\|>               # chat template turn markers
      | ^\s*(system|assistant|user)\s*:   # role prefixes at line start
      | ```                        # code fences, which end a fenced block
    )""",
    re.IGNORECASE | re.VERBOSE | re.MULTILINE,
)

FENCE_OPEN = "<untrusted_content>"
FENCE_CLOSE = "</untrusted_content>"


def neutralise(text: str) -> str:
    """Defang the sequences that let content escape its fence.

    Replaces rather than strips, so the analyst-visible meaning of the text
    survives: a post that genuinely contains "system:" still reads as such.
    """
    if not text:
        return ""
    return _INJECTION_MARKERS.sub(
        lambda m: (
            m.group(0).replace("<", "(").replace(">", ")").replace("`", "'").replace(":", " -")
        ),
        text,
    )


def fence(text: str, *, max_chars: int | None = None) -> str:
    """Return untrusted text neutralised and wrapped in a labelled fence.

    The caller states in the prompt that everything inside the fence is data
    to be described, never instructions to follow.
    """
    cleaned = neutralise(text or "")
    if max_chars is not None:
        cleaned = cleaned[:max_chars]
    return f"{FENCE_OPEN}\n{cleaned}\n{FENCE_CLOSE}"
