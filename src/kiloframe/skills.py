"""Load installed agent skills into KiloFrame's native memory-backed skill system."""

from __future__ import annotations

import re
from pathlib import Path

from .config import Settings
from .memory import MemoryStore


def _frontmatter_value(text: str, key: str) -> str:
    """Read the small YAML frontmatter subset used by Agent Skills without a YAML dep."""
    if not text.startswith("---\n"):
        return ""
    _, _, remainder = text.partition("---\n")
    header, marker, _body = remainder.partition("---\n")
    if not marker:
        return ""
    found = re.search(rf"^{re.escape(key)}:\s*[\"']?(.+?)[\"']?\s*$", header, re.MULTILINE)
    return found.group(1).strip() if found else ""


def seed_superpowers(memory: MemoryStore, root: Path) -> int:
    """Import official Superpowers skills when the installer has fetched them.

    A copied skill is available to the same relevance lookup used for KiloFrame's own
    saved procedures; it is not merely an unused checkout on disk. Re-seeding is safe:
    ``save_skill`` refines records in place.
    """
    if not root.is_dir():
        return 0
    count = 0
    for skill_path in sorted(root.glob("*/SKILL.md")):
        try:
            content = skill_path.read_text(encoding="utf-8")
        except OSError:
            continue
        name = _frontmatter_value(content, "name") or skill_path.parent.name
        description = _frontmatter_value(content, "description") or f"Use the {name} development workflow"
        memory.save_skill(f"superpowers:{name}", description, content)
        count += 1
    return count


def seed_preconfigured_skills(memory: MemoryStore, settings: Settings) -> None:
    """Seed built-in integration guides and installed Superpowers skills at daemon start."""
    playwright_skill = (
        settings.integrations_dir
        / "playwright"
        / ".agents"
        / "skills"
        / "playwright-cli"
        / "SKILL.md"
    )
    try:
        playwright_steps = playwright_skill.read_text(encoding="utf-8")
    except OSError:
        playwright_steps = (
            "Use playwright-cli for normal browser work. Inspect `playwright-cli --help` first; "
            "open a page, use snapshot-derived refs for actions, take screenshots for visual "
            "evidence, and close the browser. Use MCP only when persistent browser state is "
            "genuinely needed."
        )
    memory.save_skill(
        "playwright-cli",
        "when browser automation, UI verification, screenshots, or web test reproduction is requested",
        playwright_steps,
    )
    memory.save_skill(
        "context7",
        "when current technical documentation for a library, SDK, framework, or API is needed",
        "Use the configured Context7 MCP tools to resolve the library identifier then query current docs. "
        "If its server is unavailable, say so and use an authoritative vendor source rather than inventing an API.",
    )
    memory.save_skill(
        "serena",
        "when semantic symbol navigation, references, or safe project-wide refactoring is needed",
        "Use the configured Serena MCP server; activate the current project before semantic queries. "
        "If Serena is unavailable, use KiloFrame's file tools and report that fallback accurately.",
    )
    seed_superpowers(memory, settings.integrations_dir / "superpowers" / "skills")
