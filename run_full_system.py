#!/usr/bin/env python3
"""
PM Watchman Full System Runner

Runs the complete PM Watchman system with:
- Automatic job discovery every 6 hours
- Telegram bot for user interaction
- Job delivery scheduling
- Health monitoring
"""

import os
import sys
import asyncio
from pathlib import Path

# Add src directory to Python path
src_dir = Path(__file__).parent / "src"
sys.path.insert(0, str(src_dir))

async def main():
    """Run the full PM Watchman delivery system."""
    
    # Import delivery orchestrator
    from delivery.delivery_orchestrator import run_delivery_system_cli
    
    print("🎯 Starting PM Watchman Full Delivery System...")
    print("📱 Telegram bot + 🔄 Automatic discovery every 6 hours")
    print("🔑 Make sure TELEGRAM_BOT_TOKEN is set in environment")
    print()
    
    # Run the full system
    await run_delivery_system_cli()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 PM Watchman stopped by user")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)