#!/usr/bin/env python3
"""
PM Watchman - Main Entry Point

Automated Product Manager job search system that discovers, scores,
and delivers relevant job opportunities via Telegram.
"""

import sys
import argparse
from pathlib import Path

# Add src to Python path
sys.path.append(str(Path(__file__).parent / "src"))

from core.orchestrator import JobSearchOrchestrator


def main():
    """Main entry point for the PM job search automation system."""
    parser = argparse.ArgumentParser(description='PM Job Search Automation')
    parser.add_argument('--test', action='store_true', 
                       help='Run in test mode with single batch')
    parser.add_argument('--config-dir', default='config',
                       help='Configuration directory path')
    parser.add_argument('--data-dir', default='data',
                       help='Data storage directory path')
    
    args = parser.parse_args()
    
    orchestrator = JobSearchOrchestrator(
        config_dir=args.config_dir,
        data_dir=args.data_dir,
        test_mode=args.test
    )
    
    orchestrator.run()


if __name__ == "__main__":
    main()