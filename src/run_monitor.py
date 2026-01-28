#!/usr/bin/env python3
"""
Entry point script for EMS aircraft monitoring service.

Run this script to start monitoring for anomalies.
"""

import argparse
import sys
from pathlib import Path

# Add project root to path (for config module)
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
# Also add src directory to path (for other modules)
sys.path.insert(0, str(Path(__file__).parent))

import config
from monitor_service import MonitorService


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Monitor EMS aircraft for unusual activity patterns',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with default settings (interactive region selection)
  python src/run_monitor.py
  
  # Monitor specific region
  python src/run_monitor.py --region west
  
  # Custom polling interval
  python src/run_monitor.py --region west --interval 30
  
  # Use specific credentials file
  python src/run_monitor.py --region west --credentials credentials.json
        """
    )
    
    parser.add_argument(
        '--region',
        choices=['northeast', 'midwest', 'south', 'west', 'all'],
        default=config.MONITOR_REGION,
        help='Region to monitor (default: from config or interactive)'
    )
    
    parser.add_argument(
        '--interval',
        type=int,
        default=config.MONITOR_INTERVAL_SECONDS,
        help=f'Polling interval in seconds (default: {config.MONITOR_INTERVAL_SECONDS})'
    )
    
    parser.add_argument(
        '--credentials',
        type=Path,
        default=None,
        help='Path to OpenSky credentials file (default: credentials.json in project root)'
    )
    
    parser.add_argument(
        '--no-console',
        action='store_true',
        help='Disable console output (only log to file)'
    )
    
    parser.add_argument(
        '--database',
        choices=['ems', 'police'],
        default=None,
        help='Database type to use: ems or police (default: prompt interactively)'
    )
    
    args = parser.parse_args()
    
    # Prompt for database type if not provided
    if not args.database:
        print("\n" + "="*60)
        print("Select Database Type")
        print("="*60)
        print("1. EMS (Emergency Medical Service) aircraft")
        print("2. Police/Law Enforcement aircraft")
        print("="*60)
        
        while True:
            choice = input("Enter choice (1 or 2): ").strip()
            if choice == '1':
                args.database = 'ems'
                break
            elif choice == '2':
                args.database = 'police'
                break
            else:
                print("Invalid choice. Please enter 1 or 2.")
        print()
    
    # Validate interval
    if args.interval < 10:
        print("Warning: Polling interval less than 10 seconds may hit rate limits")
        response = input("Continue anyway? (y/N): ")
        if response.lower() != 'y':
            sys.exit(1)
    
    try:
        # Create monitor service
        service = MonitorService(
            region=args.region if args.region != 'all' else None,
            interval_seconds=args.interval,
            credentials_file=args.credentials,
            database_type=args.database
        )
        
        # Disable console output if requested
        if args.no_console:
            service.notifier.console_output = False
        
        # Run monitoring loop
        service.run_monitoring_loop()
    
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
