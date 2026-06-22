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
  "key_findings": ["<string: one finding per bullet>", ...],
  "recommendations": ["<string: one actionable recommendation>", ...],
  "confidence_level": <float 0.0-1.0 — fraction of claims backed by 2+ sources>,
  "source_citations": ["<url from CONTEXT only>", ...],
  "labels": {
    "classification": "OPEN",
    "domain": "report",
    "owner_org": "anveshak"
  }{{ legal_schema_fragment }}{{ three_lens_schema_fragment }}
}"""

_LEGAL_SCHEMA_FRAGMENT = """,
  "legal_sections": [
    {
      "finding": "<reference to a key_finding above>",
      "sections": [
        {
          "act": "<BNS|IT Act|UAPA|PMLA|NDPS>",
          "section": "<section number>",
          "description": "<short title of provision>",
          "evidence_ref": "<which source supports this mapping>",
          "labels": {"classification": "OPEN", "domain": "legal", "owner_org": "anveshak"}
        }
      ],
      "labels": {"classification": "OPEN", "domain": "legal", "owner_org": "anveshak"}
    }
  ]"""

_THREE_LENS_SCHEMA_FRAGMENT = """,
  "three_lens": {
    "evaluations": [
      {
        "perspective": "<Brigadier|NIA Chief|R&AW Chief>",
        "threat_assessment": "<1-2 sentence assessment from this perspective>",
        "priority_actions": ["<action 1>", "<action 2>"],
        "risk_level": "<LOW|MEDIUM|HIGH|CRITICAL>",
        "labels": {"classification": "OPEN", "domain": "evaluation", "owner_org": "anveshak"}
      }
    ],
    "labels": {"classification": "OPEN", "domain": "evaluation", "owner_org": "anveshak"}
  }"""


# ---------------------------------------------------------------------------
# Legal mapping instruction (injected when include_legal_mapping=True)
# ---------------------------------------------------------------------------
# REVIEW: All section numbers below must be verified by a qualified legal officer.
_LEGAL_MAPPING_INSTRUCTION = """\
LEGAL MAPPING INSTRUCTIONS:
For each key finding, identify applicable Indian legal provisions from the reference table below.
Map ONLY when evidence in CONTEXT explicitly supports the mapping. Do NOT fabricate mappings.

REFERENCE TABLE (use these exact act names and section numbers):
- BNS 318: Cheating (dishonestly inducing delivery of property)
- BNS 319: Cheating by personation
- BNS 111: Criminal conspiracy
- BNS 196: Promoting enmity between groups
- BNS 197: Imputations prejudicial to national integration
- BNS 353: Statements conducing to public mischief
- IT Act 66C: Identity theft (using electronic signature/password of another)
- IT Act 66D: Cheating by personation using computer resource
- IT Act 67: Publishing obscene material electronically
- UAPA 13: Punishment for unlawful activities
- UAPA 15: Punishment for terrorist act
- UAPA 17: Punishment for raising funds for terrorist act
- UAPA 18: Punishment for conspiracy to commit terrorist act
- UAPA 38: Offence relating to membership of a terrorist organisation
- UAPA 39: Offence relating to support given to a terrorist organisation
- PMLA 3: Offence of money laundering (proceeds of crime > Rs 1 Cr threshold)
- PMLA 4: Punishment for money laundering
- NDPS 21: Punishment for contravention in relation to manufactured drugs
- NDPS 22: Punishment for contravention in relation to psychotropic substances

IMPORTANT: These mappings are AI-generated and require verification by a qualified legal officer before use in any proceedings.
"""


# ---------------------------------------------------------------------------
# Three-lens evaluation instruction (injected when include_three_lens=True)
# ---------------------------------------------------------------------------
_THREE_LENS_INSTRUCTION = """\
THREE-LENS EVALUATION:
After producing the main report, add a "three_lens" evaluation annexure.
Evaluate the same findings from THREE distinct perspectives:

1. BRIGADIER (Operational Commander):
   - Focus: field actionability, operational timeline, force disposition
   - Risk level: based on immediate threat to personnel/assets

2. NIA CHIEF (Internal Security / Prosecution):
   - Focus: UAPA/BNS evidence chain, prosecution-ready elements, inter-state coordination
   - Risk level: based on strength of prosecution-ready evidence

3. R&AW CHIEF (External Intelligence):
   - Focus: foreign linkages, cross-border networks, strategic implications
   - Risk level: based on external threat assessment
   - If NO foreign linkage is found in the evidence, state "No foreign linkage detected in available sources" — do NOT fabricate

Each perspective must include 2-3 priority_actions specific to their domain.
"""


# ---------------------------------------------------------------------------
# Few-shot example (small, guides qwen2:7b towards correct output structure)
# ---------------------------------------------------------------------------
_FEW_SHOT_EXAMPLE = """\
EXAMPLE (for format reference only — do NOT copy this content):

Input context:
[Source: https://reuters.com/article/123 | Credibility: 72.0 | 2026-04-10]
Indian Navy conducts exercise in Arabian Sea with French Navy ships.

[Source: https://ndtv.com/india/456 | Credibility: 65.0 | 2026-04-11]
Maritime patrol aircraft spotted near Lakshadweep during joint exercise.

Output:
{
  "executive_summary": "Indian Navy conducted a joint exercise with the French Navy in the Arabian Sea on 10-11 April 2026. Maritime patrol aircraft were observed near Lakshadweep during the exercise. [Source: reuters.com] [Source: ndtv.com]",
  "key_findings": [
    "Joint naval exercise between Indian and French navies in Arabian Sea [Source: reuters.com]",
    "Maritime patrol aircraft activity near Lakshadweep islands [Source: ndtv.com]"
  ],
  "recommendations": [
    "Monitor follow-up reporting on exercise outcomes and duration",
    "Track French naval deployment schedule for repeat exercises"
  ],
  "confidence_level": 0.8,
  "source_citations": ["https://reuters.com/article/123", "https://ndtv.com/india/456"],
  "labels": {"classification": "OPEN", "domain": "report", "owner_org": "anveshak"}
}

END OF EXAMPLE. Now produce your report from the CONTEXT below.
"""


# ---------------------------------------------------------------------------
# Grounding rules (shared across all templates)
# ---------------------------------------------------------------------------
_GROUNDING_RULES = """\
STRICT RULES:
1. ONLY use facts explicitly stated in the CONTEXT section below.
2. If a fact is not in CONTEXT, write "Not confirmed in available sources."
3. Every factual claim MUST include [Source: <domain>] inline.
4. NEVER infer, speculate, or extrapolate beyond the provided CONTEXT.
5. source_citations MUST contain only URLs that appear in the CONTEXT.
6. confidence_level = fraction of key_findings backed by 2+ independent sources.
7. If CONTEXT is empty or insufficient, set confidence_level to 0.0 and state so.
"""


# ---------------------------------------------------------------------------
# Template strings
# ---------------------------------------------------------------------------

_REPORT_TEMPLATE = """\
You are {{ role }}. {{ report_type_instruction }}

{{ grounding_rules }}

{{ json_schema }}

{{ few_shot }}
{% if legal_mapping_instruction %}

{{ legal_mapping_instruction }}
{% endif %}
{% if three_lens_instruction %}

{{ three_lens_instruction }}
{% endif %}
{% if identifier_context %}

<identifier_intelligence>
{{ identifier_context }}
</identifier_intelligence>
{% endif %}

<topic>{{ topic_name }}</topic>
<keywords>{{ keywords }}</keywords>
{% if source_count > 0 %}
<context_metadata>{{ source_count }} sources, date range: {{ date_range }}</context_metadata>
{% endif %}

<context>
{{ context }}
</context>
"""


# ---------------------------------------------------------------------------
# Type-specific instructions
# ---------------------------------------------------------------------------

_TYPE_INSTRUCTIONS: dict[str, str] = {
    "intelligence_brief": (
        "Provide a concise tactical summary suitable for a senior officer. "
        "Focus on actionable intelligence, immediate threats, and key actors. "
        "Keep the executive_summary under 4 sentences. "
        "Prioritise findings by operational urgency."
    ),
    "research_summary": (
        "Provide a thorough analytical summary covering background context, "
        "key developments, and medium-term implications. "
        "Include at least 3 key_findings and 2 recommendations. "
        "Distinguish confirmed facts from single-source claims."
    ),
    "weekly_digest": (
        "Summarise the most significant developments from the past week. "
        "Highlight patterns, trends, and any emerging signals. "
        "Group findings by theme where possible. "
        "Note any developments that stopped or reversed."
    ),
}

_ROLE_MAP: dict[str, str] = {
    "intelligence_brief": "an expert intelligence analyst producing a concise tactical brief",
    "research_summary": "a research analyst producing a structured analytical summary",
    "weekly_digest": "an OSINT analyst producing a weekly intelligence digest",
}

_TEMPLATE_MAP: dict[str, str] = {
    "intelligence_brief": _REPORT_TEMPLATE,
    "research_summary": _REPORT_TEMPLATE,
    "weekly_digest": _REPORT_TEMPLATE,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def render_prompt(
    report_type: str,
    topic_name: str,
    keywords: list[str],
    context: str,
    source_count: int = 0,
    date_range: str = "",
    include_legal_mapping: bool = False,
    include_three_lens: bool = False,
    identifier_context: str = "",
) -> str:
    """Render the appropriate Jinja2 template for the given report_type.

    User-controlled values (topic_name, keywords) are injected inside XML
    boundary markers per CLAUDE.md security rule (prompt injection prevention).

    Args:
        report_type: One of intelligence_brief | research_summary | weekly_digest.
        topic_name: The user-defined topic name.
        keywords: List of topic keywords.
        context: Assembled RAG context string.
        source_count: Number of RAG sources included in context.
        date_range: Human-readable date range of context items.
        include_legal_mapping: If True, inject BNS/IT Act/UAPA/PMLA mapping instructions.
        include_three_lens: If True, inject three-lens evaluation framework instructions.
        identifier_context: Pre-formatted identifier summary for LLM context (Engine C Step 9).

    Returns:
        Rendered prompt string ready for Ollama.
    """
    template_str = _TEMPLATE_MAP[report_type]
    type_instruction = _TYPE_INSTRUCTIONS[report_type]
    role = _ROLE_MAP[report_type]
    keywords_str = ", ".join(keywords) if keywords else "(none)"

    # Build the JSON schema with optional fragments
    legal_frag = _LEGAL_SCHEMA_FRAGMENT if include_legal_mapping else ""
    three_lens_frag = _THREE_LENS_SCHEMA_FRAGMENT if include_three_lens else ""
    json_schema = _JSON_SCHEMA_INSTRUCTION.replace(
        "{{ legal_schema_fragment }}", legal_frag
    ).replace(
        "{{ three_lens_schema_fragment }}", three_lens_frag
    )

    tmpl = _env.from_string(template_str)
    return tmpl.render(
        role=role,
        report_type_instruction=type_instruction,
        grounding_rules=_GROUNDING_RULES,
        json_schema=json_schema,
        few_shot=_FEW_SHOT_EXAMPLE,
        legal_mapping_instruction=_LEGAL_MAPPING_INSTRUCTION if include_legal_mapping else "",
        three_lens_instruction=_THREE_LENS_INSTRUCTION if include_three_lens else "",
        identifier_context=identifier_context,
        topic_name=topic_name,
        keywords=keywords_str,
        context=context,
        source_count=source_count,
        date_range=date_range,
    )


# ---------------------------------------------------------------------------
# BLUF prompt — v2 data-driven reports (minimal LLM)
# ---------------------------------------------------------------------------

_BLUF_TEMPLATE = """\
You are an intelligence analyst. Write a BLUF (Bottom Line Up Front) summary.

Summarise the situation in 2-3 sentences based on the stats and cluster data below.
Be factual. Do not speculate. State only what the data shows.

<topic>{{ topic_name }}</topic>

<stats>
{{ stats_summary }}
</stats>

<clusters>
{{ cluster_summary }}
</clusters>

You MUST respond with ONLY a JSON object matching this schema (no other text):
{
  "bluf": "<string: 2-3 sentence bottom-line summary>",
  "confidence_level": <float 0.0-1.0>,
  "labels": {"classification": "OPEN", "domain": "report", "owner_org": "anveshak"}
}
"""


def render_bluf_prompt(
    topic_name: str,
    stats_summary: str,
    cluster_summary: str,
) -> str:
    """Render a short BLUF prompt for data-driven reports.

    User-controlled topic_name is wrapped in XML boundary markers
    per CLAUDE.md security rule (prompt injection prevention).
    """
    tmpl = _env.from_string(_BLUF_TEMPLATE)
    return tmpl.render(
        topic_name=topic_name,
        stats_summary=stats_summary,
        cluster_summary=cluster_summary,
    )


# ---------------------------------------------------------------------------
# Source Assessment prompt — Phase 2
# ---------------------------------------------------------------------------

_ASSESSMENT_JSON_SCHEMA = """\
You MUST respond with ONLY a JSON object matching this exact schema (no other text):
{
  "source_characterization": "<string: 2-3 sentences describing what this source is>",
  "posting_behavior": "<string: posting patterns, frequency, timing observations>",
  "key_themes": ["<string: theme 1>", "<string: theme 2>", ...],
  "narrative_role": "<originator|amplifier|aggregator>",
  "intelligence_value": "<HIGH|MEDIUM|LOW: with justification>",
  "risk_indicators": ["<string: red flag or concern>", ...],
  "cited_claims": [
    {
      "claim": "<factual statement>",
      "content_item_ids": ["<id1>", "<id2>"],
      "labels": {"classification": "OPEN", "domain": "assessment", "owner_org": "anveshak"}
    }
  ],
  "confidence_level": <float 0.0-1.0>,
  "labels": {"classification": "OPEN", "domain": "assessment", "owner_org": "anveshak"}
}"""

_ASSESSMENT_TEMPLATE = """\
You are an OSINT intelligence analyst assessing a monitored source.

RULES:
1. Only use facts present in the CONTEXT below.
2. If a fact is not in the context, do NOT invent it.
3. Every factual claim in cited_claims MUST reference specific content_item_id values from the CONTEXT.
4. narrative_role: "originator" if this source was the earliest in its narrative clusters,
   "amplifier" if it shares content from other sources, "aggregator" if it curates from multiple.
5. intelligence_value: HIGH = unique sourcing or early narrative detection,
   MEDIUM = corroborative value, LOW = noise or duplicate content.
6. risk_indicators: look for coordinated behavior, rapid topic shifts, bot-like patterns,
   propaganda markers, or suspicious identifier patterns.

<source>{{ source_name }}</source>
<platform>{{ platform }}</platform>
<topic>{{ topic_name }}</topic>
<keywords>{{ keywords }}</keywords>

{% if stats_summary %}
<stats>
{{ stats_summary }}
</stats>
{% endif %}

{% if platform_metadata %}
<profile>
{{ platform_metadata }}
</profile>
{% endif %}

<context>
{{ context }}
</context>

{{ json_schema }}
"""


def render_assessment_prompt(
    source_name: str,
    platform: str,
    topic_name: str,
    keywords: list[str],
    context: str,
    stats_summary: str = "",
    platform_metadata: str = "",
) -> str:
    """Render prompt for source assessment LLM brief.

    User-controlled values wrapped in XML boundary markers per CLAUDE.md security rule.
    """
    tmpl = _env.from_string(_ASSESSMENT_TEMPLATE)
    return tmpl.render(
        source_name=source_name,
        platform=platform,
        topic_name=topic_name,
        keywords=", ".join(keywords) if keywords else "(none)",
        context=context,
        stats_summary=stats_summary,
        platform_metadata=platform_metadata,
        json_schema=_ASSESSMENT_JSON_SCHEMA,
    )
