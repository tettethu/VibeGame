"""How a skill is invoked depends on the agent CLI: Claude reads `/name`, Codex `$name`.

Prompts are written in the Claude form -- that is what a user types, what the
dashboard's quick actions send, and what a bench task's instruction.md contains.
So every path that hands such a prompt to Codex has to rewrite it, and the
dashboard and `vibegame start` must rewrite it the same way. One table here
rather than one per caller: a skill added in only one place would work from the
dashboard and silently arrive as literal text on the CLI.
"""

# Skills a prompt may open with. Only a leading invocation is rewritten, so this
# does not need to list every skill -- just the ones a prompt is written against.
ENTRY_SKILLS = ("vibegame-start", "vibegame-build", "self-evolve")

CLAUDE_PREFIX = "/"
CODEX_PREFIX = "$"


def skill_prefix(cli: str) -> str:
    """The form to write for `cli`. Anything not Claude is addressed as Codex."""
    return CLAUDE_PREFIX if str(cli or "").startswith("claude") else CODEX_PREFIX


def skill_invocation(cli: str, skill: str) -> str:
    return f"{skill_prefix(cli)}{skill}"


def _recognised_prefix(cli: str) -> str | None:
    """Rewriting someone else's text needs certainty about the reader, so an
    unrecognised (or absent) cli yields None and the text is left alone."""
    name = str(cli or "")
    if name.startswith("claude"):
        return CLAUDE_PREFIX
    if name.startswith("codex"):
        return CODEX_PREFIX
    return None


def rewrite_leading_skill(cli: str, text: str) -> str:
    """Rewrite a leading `/skill` (or `$skill`) into the form `cli` understands.

    Only the first token, and only when it is the whole token: a prompt that
    merely mentions `/vibegame-build` mid-sentence is prose, not an invocation.
    Returns `text` unchanged when it does not open with a known skill, or when
    `cli` does not name a CLI whose form we know.
    """
    prefix = _recognised_prefix(cli)
    if prefix is None:
        return text
    stripped = text.lstrip()
    if not stripped:
        return text
    for skill in ENTRY_SKILLS:
        for written in (CLAUDE_PREFIX, CODEX_PREFIX):
            token = f"{written}{skill}"
            rest = stripped[len(token):]
            if stripped.startswith(token) and (not rest or rest[0].isspace()):
                return f"{prefix}{skill}" + rest
    return text
