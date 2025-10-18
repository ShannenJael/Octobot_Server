"""Minimal evaluator API stub for local development.

Provides tiny helpers used by the core to enumerate evaluator classes.
All functions return empty lists or simple placeholders so OctoBot can run
without evaluator functionality.
"""

def get_evaluator_classes_from_type(evaluator_type, tentacle_setup_config=None):
    # Return an empty list — no evaluators available in stub mode
    return []


def get_evaluator_class(name):
    return None
