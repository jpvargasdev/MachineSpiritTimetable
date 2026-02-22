#!/usr/bin/env python3
"""XyaoLED - Display SL departures on LED matrix.

Usage:
    # Display next departure to Ropsten from site 9293
    python3 -m src.main --site 9293
    
    # With custom refresh interval
    python3 -m src.main --site 9293 --interval 60
    
    # Manual text mode
    python3 -m src.main --text "Hello World" --color red
    
    # Preview mode (no device needed)
    python3 -m src.main --site 9293 --preview
"""

import argparse
import asyncio
import signal

from infra import Screen
from infra.bitmap import COLORS
from domain import SLApi
from formatters import format_two_lines


# Default site ID
DEFAULT_SITE_ID = 9293


# Flag for graceful shutdown
running = True


def signal_handler(sig, frame):
    """Handle Ctrl+C for graceful shutdown."""
    global running
    print("\nShutting down...")
    running = False


async def run_departure_display(
    site_id: int,
    interval: int = 30,
    color: str = "red",
    preview: bool = False,
    scroll: bool = False
):
    """Run the departure display loop.
    
    Args:
        site_id: SL site ID
        interval: Refresh interval in seconds
        color: Display color
        preview: Preview mode (no device)
    """
    global running
    
    api = SLApi()
    screen = Screen() if not preview else None
    
    try:
        if screen:
            print("Connecting to LED display...")
            await screen.connect()
            print("Connected!")
        
        print(f"Fetching departures for site {site_id} every {interval}s")
        print("Press Ctrl+C to stop\n")
        
        while running:
            try:
                # Fetch departures
                response = await api.get_departures(site_id)
                
                # Format first departure as line 1
                if response.departures:
                    dep1 = response.departures[0]
                    line1 = f"{dep1.destination}"
                    line2 = f"{dep1.display}"
                else:
                    line1 = "No departures"
                    line2 = ""  
                
                print(f"[{response.stop_name or site_id}] {line1} | {line2}")
                
                # Always show ASCII preview in terminal
                temp_screen = Screen()
                ascii_art = await temp_screen.render_two_lines(line1, line2, color=color, use_medium=True, preview=True)
                print(ascii_art)
                
                if screen:
                    # Send to device with scroll animation
                    await screen.render_two_lines(
                        line1, line2,
                        color=color,
                        scroll=scroll,
                        use_medium=True,
                    )

                             
            except Exception as e:
                print(f"Error: {e}")
            
            # Wait for next refresh
            for _ in range(interval):
                if not running:
                    break
                await asyncio.sleep(1)
    
    finally:
        await api.close()
        if screen:
            await screen.disconnect()
            print("Disconnected.")


async def run_text_mode(
    text: str,
    color: str = "red",
    scroll: bool = False,
    speed: int = 60,
    brightness: int = 255,
    scale: int = 1,
    preview: bool = False
):
    """Run in manual text mode.
    
    Args:
        text: Text to display
        color: Display color
        scroll: Enable scrolling
        speed: Scroll speed
        brightness: Display brightness
        scale: Font scale
        preview: Preview mode
    """
    if preview:
        screen = Screen()
        ascii_art = await screen.render(
            text,
            color=color,
            scale=scale,
            preview=True
        )
        print(f"Text: '{text}'")
        print(f"Color: {color}")
        print(f"Scroll: {scroll}")
        print()
        print(ascii_art)
        return
    
    print("Connecting to LED display...")
    async with Screen() as screen:
        print("Connected!")
        print(f"Sending: '{text}'")
        
        await screen.render(
            text,
            color=color,
            scroll=scroll,
            speed=speed,
            brightness=brightness,
            scale=scale
        )
        
        print("Sent! Check device.")
        await asyncio.sleep(2)
    
    print("Disconnected.")


async def main():
    parser = argparse.ArgumentParser(
        description="Display SL departures or custom text on XyaoLED"
    )
    
    # Mode selection
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--site", type=int, nargs="?", const=DEFAULT_SITE_ID,
                      help=f"SL site ID (default: {DEFAULT_SITE_ID})")
    mode.add_argument("--text", "-t",
                      help="Manual text to display")
    
    # Common options
    parser.add_argument("--color", "-c", default="red",
                        choices=list(COLORS.keys()),
                        help="Display color (default: red)")
    parser.add_argument("--scroll", action="store_true",
                        help="Enable scrolling animation")
    parser.add_argument("--preview", "-p", action="store_true",
                        help="Preview only (don't send to device)")
    
    # Departure mode options
    parser.add_argument("--interval", "-i", type=int, default=30,
                        help="Refresh interval in seconds (default: 30)")
    
    # Text mode options
    parser.add_argument("--size", "-s", default="small",
                        choices=["small", "large"],
                        help="Font size (default: small)")
    parser.add_argument("--speed", type=int, default=60,
                        help="Scroll speed 1-255 (default: 60)")
    parser.add_argument("--brightness", type=int, default=255,
                        help="Brightness 0-255 (default: 255)")
    
    args = parser.parse_args()
    
    # Setup signal handler
    signal.signal(signal.SIGINT, signal_handler)
    
    if args.site is not None:
        # Departure display mode
        await run_departure_display(
            site_id=args.site,
            interval=args.interval,
            color=args.color,
            preview=args.preview
        )
    else:
        # Manual text mode
        scale = 2 if args.size == "large" else 1
        await run_text_mode(
            text=args.text,
            color=args.color,
            scroll=args.scroll,
            speed=args.speed,
            brightness=args.brightness,
            scale=scale,
            preview=args.preview
        )


if __name__ == "__main__":
    asyncio.run(main())
