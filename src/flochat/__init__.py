"""FloChat - Your Live Chat, Always Within Reach.

This build provides the shared core, explicit platform-adapter boundaries, the
installation and launch scripts, and the engineering standards documented in the
root README.md. Read-only YouTube integration requires explicit OAuth setup.
Individual writes require the authoritative safety session and fresh bound approval.
Optional floating clients use authenticated local IPC; background availability never posts.
"""

__version__ = "0.1.0"
__all__ = ["__version__"]
