"""Standard-library JSON API for the AgentForge Phase 3 MVP."""

from agentforge.web.app import create_server, run_server
from agentforge.web.routes import WebResponse, handle_request

__all__ = ["WebResponse", "create_server", "handle_request", "run_server"]
