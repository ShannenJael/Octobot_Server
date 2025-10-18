"""Evaluators package stub.

Expose the channel submodule so imports like
`import octobot_evaluators.evaluators as evaluators` still allow
access to evaluators.channel.get_chan.
"""

from . import channel  # noqa: F401

__all__ = ["channel"]
