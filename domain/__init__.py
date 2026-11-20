"""Pasto10 domain — the DomainSpec that Semente assembles into the app.

Exposes ``domain_spec``: the area registration, pasture and biomass tools, the
animal-unit skill (``domain/skills/livestock``), the input guardrails
(``domain.guardrails``) and the dynamic tool/instruction callables
(``domain.agent``) driven by the registration state machine.

Tool modules resolve their descriptions from ``domain/prompts/tools.yml`` at
import time. The Semente app applies the manifest's ``prompts_dir`` before
importing the domain; ``SEMENTE_PROMPTS_DIR`` is defaulted here so that a
bare ``import domain`` (scripts, REPL) finds the same prompts. An explicit
env var or ``set_prompts_dir`` call still takes precedence.
"""

import os
from pathlib import Path

os.environ.setdefault("SEMENTE_PROMPTS_DIR", str(Path(__file__).resolve().parent / "prompts"))

from semente import DomainSpec  # noqa: E402
from semente.logging import log_warning  # noqa: E402
from semente.skills import load_skills  # noqa: E402

from domain.agent import get_instructions, get_tools  # noqa: E402
from domain.guardrails import guardrails  # noqa: E402
from domain.vertex_compat import install as install_vertex_compat  # noqa: E402

# Lets tool results that carry images (area maps) work on Vertex AI too
install_vertex_compat()

skills = load_skills(Path(__file__).resolve().parent / "skills" / "livestock")
if skills is None:
    log_warning("domain: no skills were loaded from domain/skills/livestock")

domain_spec = DomainSpec(
    name="Pasto Bacano",
    tools=get_tools,
    skills=skills,
    guardrails=guardrails,
    instructions=get_instructions,
)
