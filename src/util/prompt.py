"""Shared prompt-loading helper.

Used by CLI entries that accept a `-t/--text` parameter which can be either
a literal prompt string or a path to a text file. Keeps behavior identical
across `vibegame vlm`, `vibegame art gen image`, `vibegame art gen video`.
"""

from pathlib import Path

TEXT_EXTENSION_LIST = (".txt", ".md", ".log", ".rst")
TEXT_EXTENSIONS = set(TEXT_EXTENSION_LIST)


class UnsupportedPromptFileFormat(ValueError):
    pass


def load_prompt(text: str, label: str = "prompt") -> str:
    """Return prompt text, or read an existing supported prompt file.

    Prints a one-line indicator at the start so the caller can see whether the
    value was interpreted as a file path or as a raw literal.
    """
    if not text:
        return text
    # Fast literal rejection: newlines or very long strings cannot be real
    # paths (OS filename limit is ~255 bytes). Skip the filesystem check so
    # large multi-line prompts do not blow up on Path.stat().
    if "\n" in text or len(text) > 255:
        print(f"Using raw text as {label}")
        return text
    try:
        p = Path(text)
        is_file = p.exists() and p.is_file()
    except OSError:
        # Path too long, illegal chars, etc. — treat as literal.
        is_file = False
    if is_file:
        suffix = p.suffix.lower()
        if suffix not in TEXT_EXTENSIONS:
            supported = ", ".join(TEXT_EXTENSION_LIST)
            raise UnsupportedPromptFileFormat(
                f"Not in supported file format, please use {supported}: {p}"
            )
        print(f"Loaded {label} from {p}")
        return p.read_text(encoding="utf-8").strip()
    print(f"Using raw text as {label}")
    return text
