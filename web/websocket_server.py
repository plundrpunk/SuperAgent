#!/usr/bin/env python3
"""
Standalone WebSocket Server for SuperAgent Event Streaming.

This server listens for events published to a Redis channel ('agent-events')
and broadcasts them to all connected WebSocket clients, such as the SuperAgent dashboard.
"""
import asyncio
import os
import sys
from pathlib import Path

# Add the project root to the Python path to allow for absolute imports
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from agent_system.observability.event_stream import EventEmitter, Colors
except ImportError as e:
    print(f"Error: Failed to import SuperAgent modules. Make sure you're running this from the project root.")
    print(f"Details: {e}")
    sys.exit(1)

WEBSOCKET_PORT = 3010

async def main():
    """
    Initializes and runs the EventEmitter server.
    """
    print("""
╔══════════════════════════════════════════════════════════════╗
║           SuperAgent WebSocket Server                       ║
╚══════════════════════════════════════════════════════════════╝
""")
    
    # Initialize the EventEmitter
    # It will automatically handle WebSocket, Redis subscription, and console logging.
    emitter = EventEmitter(
        websocket_enabled=True,
        websocket_port=WEBSOCKET_PORT,
        console_enabled=True,  # Log events to console for debugging
        file_enabled=True      # Also write events to log files
    )

    # Start the server and its background tasks (Redis listener)
    await emitter.start()

    print(f"\n{Colors.SUCCESS}✅ Event streaming server is now running.{Colors.RESET}")
    print(f"   - WebSocket clients can connect to: ws://localhost:{WEBSOCKET_PORT}")
    print(f"   - Listening for events on Redis channel: 'agent-events'")
    print(f"\nPress Ctrl+C to stop the server.")

    try:
        # Keep the server running indefinitely
        while True:
            await asyncio.sleep(3600)  # Sleep for an hour, or until interrupted
    except asyncio.CancelledError:
        print(f"\n{Colors.WARNING}Server task cancelled.{Colors.RESET}")
    finally:
        # Gracefully shut down the emitter
        print(f"\n{Colors.INFO}Shutting down event server...{Colors.RESET}")
        await emitter.stop()
        print(f"{Colors.SUCCESS}Server shutdown complete.{Colors.RESET}")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{Colors.WARNING}Keyboard interrupt received. Exiting.{Colors.RESET}")
