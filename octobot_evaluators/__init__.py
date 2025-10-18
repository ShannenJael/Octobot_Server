"""Lightweight local stub for octobot_evaluators used for local dev/testing.

This stub provides the minimal API surface required by the OctoBot core to
import evaluator channels without depending on the external OctoBot-Evaluators
package and tulipy native build. It's intentionally tiny and returns no-op
channel objects. Remove or replace this with the real package for production
or full evaluator functionality.
"""

__all__ = ["evaluators"]
