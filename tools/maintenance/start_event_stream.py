#!/usr/bin/env python3
"""
Standalone event stream server startup script.

Properly initializes Redis subscriber for relaying events from Kaya CLI to WebSocket.
"""
import asyncio
from agent_system.observability.event_stream import EventEmitter, Colors

async def main():
    """Start event stream server with Redis subscriber enabled."""
    print(f"{Colors.INFO}Starting SuperAgent Event Stream Server...{Colors.RESET}")

    # Create emitter with all features enabled
    emitter = EventEmitter(
        websocket_enabled=True,
        websocket_port=3010,
        console_enabled=True,
        file_enabled=True,
        enable_log_rotation=True,
        compress_after_days=7,
        delete_after_days=30
    )

    # Start emitter (this starts WebSocket server and Redis subscriber)
    await emitter.start()

    print(f"\n{Colors.SUCCESS}Event streaming system started!{Colors.RESET}\n")
    print(f"WebSocket server: ws://localhost:3010/agent-events")
    print(f"Log directory: {emitter.log_dir}")
    print(f"\n{Colors.INFO}Event stream running. Press Ctrl+C to stop.{Colors.RESET}\n")

    # Keep running
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print(f"\n{Colors.WARNING}Shutting down...{Colors.RESET}")
        await emitter.stop()

if __name__ == '__main__':
    asyncio.run(main())
