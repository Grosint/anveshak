"""Jinja2-based prompt templates for LLM report generation.

CLAUDE.md security rule: user input (topic name, keywords) is wrapped in XML
boundary markers (<topic>, <keywords>, <context>) so the LLM cannot confuse
user-controlled data with system instructions.

CLAUDE.md rule 9: prompts specify the exact JSON schema matching ReportContent
so output can be parsed by Pydantic before any storage.
"""
from __future__ import annotations

from jinja2 import Environment, Undefined

# ---------------------------------------------------------------------------
# Jinja2 environment (no filesystem — inline templates only)
# ---------------------------------------------------------------------------
_env = Environment(undefined=Undefined, autoescape=False)  # nosec B701 — LLM text prompts, not HTML; autoescape would corrupt <topic>/<context> boundary markers required by CLAUDE.md rule 9


# ---------------------------------------------------------------------------
# Shared JSON schema instruction (injected into every template)
# ---------------------------------------------------------------------------
_JSON_SCHEMA_INSTRUCTION = """\
You MUST respond with ONLY a JSON object matching this exact schema (no other text):
{
  "executive_summary": "<string: 2-4 sentences>",
  "key_findings": ["<string>", ...],
  "recommendations": ["<string>", ...],
  "confidence_level": <float 0.0-1.0>,
  "source_citations": ["<url>", ...],
  "labels": {
    "classification": "OPEN",
    "domain": "report",
    "owner_org": "anveshak"
  }
}"""


# ---------------------------------------------------------------------------
# Template strings
# ---------------------------------------------------------------------------

INTELLIGENCE_BRIEF_TEMPLATE = """\
You are an expert intelligence analyst. Produce a concise intelligence brief.

{{ report_type_instruction }}

{{ json_schema }}

<topic>{{ topic_name }}</topic>
<keywords>{{ keywords }}</keywords>

<context>
{{ context }}
</context>

Only use information from the CONTEXT section. Do not hallucinate.
Cite only URLs that appear in the CONTEXT section.
"""

RESEARCH_SUMMARY_TEMPLATE = """\
You are a research analyst. Produce a structured research summary.

{{ report_type_instruction }}

{{ json_schema }}

<topic>{{ topic_name }}</topic>
<keywords>{{ keywords }}</keywords>

<context>
{{ context }}
</context>

Only use information from the CONTEXT section. Do not hallucinate.
Cite only URLs that appear in the CONTEXT section.
"""

WEEKLY_DIGEST_TEMPLATE = """\
You are an OSINT analyst producing a weekly digest.

{{ report_type_instruction }}

{{ json_schema }}

<topic>{{ topic_name }}</topic>
<keywords>{{ keywords }}</keywords>

<context>
{{ context }}
</context>

Only use information from the CONTEXT section. Do not hallucinate.
Cite only URLs that appear in the CONTEXT section.
"""


# ---------------------------------------------------------------------------
# Type-specific instructions
# ---------------------------------------------------------------------------

_TYPE_INSTRUCTIONS: dict[str, str] = {
    "intelligence_brief": (
        "Provide a concise tactical summary suitable for a senior officer. "
        "Focus on actionable intelligence, immediate threats, and key actors."
    ),
    "research_summary": (
        "Provide a thorough analytical summary covering background context, "
        "key developments, and medium-term implications."
    ),
    "weekly_digest": (
        "Summarise the most significant developments from the past week. "
        "Highlight patterns, trends, and any emerging signals."
    ),
}

_TEMPLATE_MAP: dict[str, str] = {
    "intelligence_brief": INTELLIGENCE_BRIEF_TEMPLATE,
    "research_summary": RESEARCH_SUMMARY_TEMPLATE,
    "weekly_digest": WEEKLY_DIGEST_TEMPLATE,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def render_prompt(
    report_type: str,
    topic_name: str,
    keywords: list[str],
    context: str,
) -> str:
    """Render the appropriate Jinja2 template for the given report_type.

    User-controlled values (topic_name, keywords) are injected inside XML
    boundary markers per CLAUDE.md security rule (prompt injection prevention).

    Args:
        report_type: One of intelligence_brief | research_summary | weekly_digest.
        topic_name: The user-defined topic name.
        keywords: List of topic keywords.
        context: Assembled RAG context string.

    Returns:
        Rendered prompt string ready for Ollama.
    """
    template_str = _TEMPLATE_MAP.get(report_type, INTELLIGENCE_BRIEF_TEMPLATE)
    type_instruction = _TYPE_INSTRUCTIONS.get(
        report_type, _TYPE_INSTRUCTIONS["intelligence_brief"]
    )
    keywords_str = ", ".join(keywords) if keywords else "(none)"

    tmpl = _env.from_string(template_str)
    return tmpl.render(
        report_type_instruction=type_instruction,
        json_schema=_JSON_SCHEMA_INSTRUCTION,
        topic_name=topic_name,
        keywords=keywords_str,
        context=context,
    )
