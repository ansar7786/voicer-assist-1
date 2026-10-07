"""
Tool declarations and handlers for SIH26097 Voice Assistant.
"""
from typing import Dict, Any

def handle_ping(args: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "status": "pong",
        "message": args.get("message", "pong"),
    }
