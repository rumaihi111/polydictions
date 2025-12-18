"""
Main Entry Point for Polydictor

Combines original Polydictions features with new Polydictor intelligence platform.
Run this file to start the complete system.
"""

import asyncio
import logging
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('polydictor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


async def main():
    """
    Main entry point that starts:
    1. Original Polydictions bot (event monitoring, /deal, etc.)
    2. Polydictor intelligence system (agents, Twitter streams)
    3. API server for Chrome extension
    """
    logger.info("=" * 60)
    logger.info("POLYDICTOR - Agentic Twitter Intelligence Platform")
    logger.info("=" * 60)
    
    try:
        # Import bot components
        from bot import PolydictionsBot
        from api_server import APIServer
        from polydictor_bot import polydictor_router
        from agent import agent_manager
        import os
        
        # Get bot token
        token = os.getenv('BOT_TOKEN')
        if not token:
            logger.error("BOT_TOKEN not found in .env!")
            return
        
        # Create bot instance
        polydictions_bot = PolydictionsBot(token.strip())
        
        # Register Polydictor router with dispatcher
        polydictions_bot.dp.include_router(polydictor_router)
        
        logger.info("✓ Polydictor intelligence features loaded")
        logger.info("✓ Original Polydictions features loaded")
        
        # Restore any active agents from disk
        logger.info(f"Loaded {len(agent_manager.agents)} saved agents")
        
        # Restart active agents
        for event_slug, agent in agent_manager.agents.items():
            if agent.status == "active":
                logger.info(f"Restarting agent: {event_slug}")
                try:
                    await agent_manager.start_agent(event_slug)
                except Exception as e:
                    logger.error(f"Failed to restart agent {event_slug}: {e}")
        
        # Note: API server disabled for now (conflicts with bot event loop)
        # You can run api_server.py separately if needed
        
        # Start bot (includes original features + Polydictor)
        logger.info("Starting Telegram bot...")
        logger.info("")
        logger.info("Available Commands:")
        logger.info("  Original Polydictions:")
        logger.info("    /start - Subscribe to new events")
        logger.info("    /deal - Analyze Polymarket event")
        logger.info("    /keywords - Set filters")
        logger.info("    /pause - Pause notifications")
        logger.info("")
        logger.info("  Polydictor Intelligence:")
        logger.info("    /watch - Start event monitoring")
        logger.info("    /verify - Verify payment")
        logger.info("    /mystatus - View subscriptions")
        logger.info("    /unwatch - Cancel subscription")
        logger.info("")
        logger.info("=" * 60)
        
        # Run bot (this blocks)
        await polydictions_bot.start()
        
    except KeyboardInterrupt:
        logger.info("\nShutting down...")
        
        # Stop all agents
        for event_slug in list(agent_manager.agents.keys()):
            await agent_manager.stop_agent(event_slug)
        
        logger.info("✓ All agents stopped")
        logger.info("Goodbye!")
        
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
