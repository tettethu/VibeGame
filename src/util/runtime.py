"""Runtime constants shared by the CLI and the standalone runtime server.

Kept here rather than in `cli.run` so the server process can read them without
importing the whole typer CLI tree (~1.5 s).
"""

DEFAULT_RUNTIME_PORT = 8765
