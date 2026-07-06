"""Central model configuration for the GovAgent-IQ agent graph.

Keeping the model name in one place lets us swap models (or route different
agents to different tiers) without editing each agent module. Override at runtime
with the GEMINI_MODEL environment variable.
"""

import os

MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
