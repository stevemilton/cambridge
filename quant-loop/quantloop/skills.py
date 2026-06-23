"""Piece #2 — The skill.

A skill is a procedure manual the worker reads instead of being told from
scratch every session. It lives in a SKILL.md file: conventions, rules, and a
"lessons learned" log ("we don't do it like this because of that one incident").

Without skills, every loop run starts from zero. With skills, intent compounds —
and crucially, the loop can *write new lessons back* after a loss, so the same
mistake is encoded as a rule before the next run. That write-back is what makes
the system self-improving.

A SKILL.md is parsed into sections by markdown headings. The two sections the
loop cares about are `Rules` (active constraints) and `Lessons learned`
(append-only history). `append_lesson()` adds to both — a dated note in the log
and, optionally, a promoted rule.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import date


_HEADING_RE = re.compile(r"^#{1,6}\s+(.*?)\s*$")
_BULLET_RE = re.compile(r"^\s*[-*]\s+(.*?)\s*$")


@dataclass
class Skill:
    name: str
    path: str
    sections: dict[str, list[str]] = field(default_factory=dict)
    raw: str = ""

    @property
    def goal(self) -> str:
        lines = self.sections.get("Goal", [])
        return " ".join(lines).strip()

    @property
    def rules(self) -> list[str]:
        return list(self.sections.get("Rules", []))

    @property
    def lessons(self) -> list[str]:
        return list(self.sections.get("Lessons learned", []))

    def append_lesson(self, lesson: str, new_rule: str | None = None,
                      on: date | None = None) -> None:
        """Write a lesson (and optionally promote a new rule) back to SKILL.md.

        This is the self-improving step: every loss becomes a dated lesson, and
        every lesson can become a rule the next run is bound by.
        """
        stamp = (on or date.today()).isoformat()
        entry = f"- {stamp}: {lesson}"
        if new_rule:
            entry += f"\n  New rule: {new_rule}"
        text = self.raw.rstrip() + "\n"
        if "## Lessons learned" in text:
            text += f"{entry}\n"
        else:
            text += f"\n## Lessons learned\n{entry}\n"
        if new_rule:
            # Promote the rule into the active Rules section so it binds next run.
            text = _insert_rule(text, new_rule)
        with open(self.path, "w") as fh:
            fh.write(text)
        self.raw = text
        self.sections = _parse_sections(text)


def load_skill(path: str) -> Skill:
    """Load and parse a SKILL.md file into a Skill the worker can consult."""
    with open(path) as fh:
        raw = fh.read()
    name = os.path.splitext(os.path.basename(path))[0]
    return Skill(name=name, path=path, sections=_parse_sections(raw), raw=raw)


def _parse_sections(text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current = None
    for line in text.splitlines():
        heading = _HEADING_RE.match(line)
        if heading:
            current = heading.group(1)
            sections.setdefault(current, [])
            continue
        if current is None:
            continue
        bullet = _BULLET_RE.match(line)
        if bullet:
            sections[current].append(bullet.group(1))
        elif line.strip():
            sections[current].append(line.strip())
    return sections


def _insert_rule(text: str, rule: str) -> str:
    lines = text.splitlines()
    out: list[str] = []
    inserted = False
    in_rules = False
    for line in lines:
        heading = _HEADING_RE.match(line)
        if heading:
            if in_rules and not inserted:
                out.append(f"- {rule}")
                inserted = True
            in_rules = heading.group(1) == "Rules"
        out.append(line)
    if in_rules and not inserted:
        out.append(f"- {rule}")
        inserted = True
    return "\n".join(out) + "\n"
