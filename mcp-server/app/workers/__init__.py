"""Process entrypoints (composition roots) for out-of-server worker processes.

Each module here is the composition root of a standalone worker container — the
worker analogue of ``app/main.py`` for the server. It reads its own environment,
constructs every concrete collaborator, and runs the worker loop. Subsystem
modules never import from here (dependency direction: composition root ->
subsystem, never the reverse).
"""
