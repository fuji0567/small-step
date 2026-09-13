"""MCP server run beside the local microphone / GPU worker, not the public API."""

from __future__ import annotations

import argparse
import ipaddress
from typing import Protocol

from mcp.server import MCPServer

from app.config import Settings, get_settings
from app.edge_audio import EdgeAudioCandidate, EdgeAudioProcessor, SubmittedRecord


class EdgeAudioService(Protocol):
    def status(self) -> dict[str, object]: ...

    def analyze_audio_file(self, audio_path: str) -> EdgeAudioCandidate: ...

    def submit_analyzed_audio_file(self, *, audio_path: str, child_id: str | None = None) -> SubmittedRecord: ...


def build_mcp_server(
    *,
    service: EdgeAudioService | None = None,
    settings: Settings | None = None,
) -> MCPServer:
    """Build an injectable server so its tools can be tested in memory."""

    runtime_settings = settings or get_settings()
    edge_audio = service or EdgeAudioProcessor(settings=runtime_settings)
    mcp = MCPServer(
        "Small Step Edge Audio",
        instructions=(
            "Use only files already placed in the configured local audio inbox. "
            "Audio is processed locally and deleted by default. Submitting a candidate "
            "creates a teacher-review record only for a concrete event; it never sends a LINE message."
        ),
    )

    @mcp.tool()
    def edge_audio_status() -> dict[str, object]:
        """Show safe configuration readiness without returning API keys or audio content."""

        return edge_audio.status()

    @mcp.tool()
    def analyze_audio_file(audio_path: str) -> dict[str, object]:
        """Create an anonymous candidate from a local audio file without writing to the API."""

        return edge_audio.analyze_audio_file(audio_path).model_dump(mode="json")

    @mcp.tool()
    def submit_analyzed_audio_file(audio_path: str, child_id: str | None = None) -> dict[str, object]:
        """Create a pending-review record only for a concrete event; a teacher must still approve it."""

        return edge_audio.submit_analyzed_audio_file(audio_path=audio_path, child_id=child_id).as_dict()

    return mcp


mcp = build_mcp_server()


def is_loopback_host(host: str) -> bool:
    """Keep the unauthenticated MCP HTTP transport off the public network."""

    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Small Step local edge-audio MCP server")
    parser.add_argument("--streamable-http", action="store_true", help="Serve MCP over local HTTP instead of stdio")
    parser.add_argument("--host", default="127.0.0.1", help="HTTP host when --streamable-http is set")
    parser.add_argument("--port", default=8002, type=int, help="HTTP port when --streamable-http is set")
    args = parser.parse_args()
    if args.streamable_http:
        if not is_loopback_host(args.host):
            raise SystemExit("The MCP HTTP server must bind to localhost or a loopback IP address")
        mcp.run(transport="streamable-http", host=args.host, port=args.port)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
