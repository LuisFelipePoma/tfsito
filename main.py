import argparse
import sys
import spade
from src.config import config
from src.utils.logger import logger
from src.agent.coordinator import launch_agent_coordinator
from src.agent.taxi import launch_agent_taxi
from src.services.openfire_api import openfire_api

def main():
    """Main entry point"""
    
    parser = argparse.ArgumentParser(description="Taxi Multi-Agent System")
    parser.add_argument("--host", type=str, required=True, help="Hostname identifier")
    parser.add_argument(
        "--agent-count",
        type=int,
        default=10,
        help="Number of agents to spawn on this host",
    )
    parser.add_argument("--openfire-host", type=str, help="Openfire server hostname")
    parser.add_argument("--openfire-port", type=int, help="Openfire server port")
    parser.add_argument(
        "--agent-type", type=str, help="Agent Type (Taxi / Coordinator)"
    )

    args = parser.parse_args()

    # Override config with command line args
    if args.host:
        config.host_name = args.host
    if args.openfire_host:
        config.openfire_host = args.openfire_host
    if args.openfire_port:
        config.openfire_port = args.openfire_port

    print(f"Openfire server: {config.openfire_host}:{config.openfire_port}")
    print(f"Grid size: {config.grid_width}x{config.grid_height}")

    try:
        if args.agent_type == "taxi":
            result = spade.run(launch_agent_taxi(args.agent_count))
            sys.exit(result)
        else:
            users = openfire_api.list_users()
            for user in users:
                if user != "admin":
                    openfire_api.delete_user(user)
            launch_agent_coordinator()
    except KeyboardInterrupt:
        print("\nShutdown requested by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    sys.exit(main())