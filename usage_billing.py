"""
Usage-Based Billing System

Pay-as-you-go model:
- Grok API usage: Variable cost based on actual API calls
- TwitterAPI.io: Flat $2 USDC per 24 hours per active event
- All charges auto-deducted from user's prepaid wallet
"""

import os
import json
import logging
from typing import Dict, Optional
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

USAGE_TRACKING_FILE = "usage_tracking.json"

# Pricing Configuration
GROK_COST_PER_CALL = 0.01  # $0.01 per Grok API call (estimate)
TWITTER_API_DAILY_FEE = 2.0  # $2 USDC per 24 hours per event
PLATFORM_WALLET_ADDRESS = os.getenv("PLATFORM_WALLET_ADDRESS", "55BSkfcQM2QGA7HHNu13iY5SJB7KYvWJ2NgQJSthbHAE")


class UsageBilling:
    """
    Tracks usage and bills users accordingly.
    
    Usage Types:
    1. Grok API calls - pay per call
    2. TwitterAPI.io - pay per 24h period per event
    
    All charges deducted from user's prepaid Solana wallet.
    """
    
    def __init__(self, payment_system):
        self.payment_system = payment_system
        self.usage_data: Dict = {}  # user_id -> {event_slug -> usage_stats}
        self.load_usage_data()
    
    def load_usage_data(self):
        """Load usage tracking data"""
        if Path(USAGE_TRACKING_FILE).exists():
            try:
                with open(USAGE_TRACKING_FILE, 'r') as f:
                    self.usage_data = json.load(f)
                logger.info(f"Loaded usage data for {len(self.usage_data)} users")
            except Exception as e:
                logger.error(f"Error loading usage data: {e}")
    
    def save_usage_data(self):
        """Save usage tracking data"""
        try:
            with open(USAGE_TRACKING_FILE, 'w') as f:
                json.dump(self.usage_data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving usage data: {e}")
    
    def init_event_tracking(self, user_id: int, event_slug: str):
        """Initialize tracking for a new event"""
        user_id_str = str(user_id)
        
        if user_id_str not in self.usage_data:
            self.usage_data[user_id_str] = {}
        
        self.usage_data[user_id_str][event_slug] = {
            "started_at": datetime.utcnow().isoformat(),
            "last_billing_cycle": datetime.utcnow().isoformat(),
            "grok_calls": {
                "analyze_tweet": 0,
                "synthesize_digest": 0,
                "refine_ruleset": 0
            },
            "total_grok_calls": 0,
            "total_grok_cost": 0.0,
            "twitter_api_days": 1,  # First day
            "twitter_api_cost": TWITTER_API_DAILY_FEE,
            "total_cost": TWITTER_API_DAILY_FEE,
            "last_charge": datetime.utcnow().isoformat()
        }
        
        self.save_usage_data()
        logger.info(f"Initialized usage tracking for user {user_id}, event {event_slug}")
    
    def record_grok_call(self, user_id: int, event_slug: str, call_type: str):
        """
        Record a Grok API call for billing.
        
        Args:
            call_type: 'analyze_tweet', 'synthesize_digest', or 'refine_ruleset'
        """
        user_id_str = str(user_id)
        
        if user_id_str not in self.usage_data or event_slug not in self.usage_data[user_id_str]:
            logger.warning(f"No usage tracking for user {user_id}, event {event_slug}")
            return
        
        event_data = self.usage_data[user_id_str][event_slug]
        
        # Increment counters
        if call_type in event_data["grok_calls"]:
            event_data["grok_calls"][call_type] += 1
        
        event_data["total_grok_calls"] += 1
        event_data["total_grok_cost"] += GROK_COST_PER_CALL
        event_data["total_cost"] += GROK_COST_PER_CALL
        
        self.save_usage_data()
        
        logger.debug(f"Recorded Grok {call_type} for user {user_id}, event {event_slug} (+${GROK_COST_PER_CALL})")
    
    async def check_and_charge_daily_fee(self, user_id: int, event_slug: str) -> Dict:
        """
        Check if 24 hours has passed and charge daily TwitterAPI.io fee.
        Called periodically by the agent.
        
        Returns: {charged: bool, amount: float, message: str}
        """
        user_id_str = str(user_id)
        
        if user_id_str not in self.usage_data or event_slug not in self.usage_data[user_id_str]:
            return {"charged": False, "amount": 0.0, "message": "No usage tracking found"}
        
        event_data = self.usage_data[user_id_str][event_slug]
        last_cycle = datetime.fromisoformat(event_data["last_billing_cycle"])
        now = datetime.utcnow()
        
        # Check if 24 hours has passed
        if now - last_cycle < timedelta(hours=24):
            return {"charged": False, "amount": 0.0, "message": "Not yet 24 hours"}
        
        # Time to charge daily fee
        balance = await self.payment_system.check_user_balance(user_id)
        
        if balance < TWITTER_API_DAILY_FEE:
            # Insufficient balance - stop the agent
            logger.warning(f"User {user_id} insufficient balance for daily fee. Stopping event {event_slug}")
            return {
                "charged": False,
                "amount": 0.0,
                "message": f"Insufficient balance. Need {TWITTER_API_DAILY_FEE} USDC for next 24h",
                "should_stop": True
            }
        
        # Charge the daily fee
        transfer_result = await self.payment_system.transfer_usdc_to_platform(
            user_id,
            TWITTER_API_DAILY_FEE
        )
        
        if transfer_result["success"]:
            # Update tracking
            event_data["last_billing_cycle"] = now.isoformat()
            event_data["twitter_api_days"] += 1
            event_data["twitter_api_cost"] += TWITTER_API_DAILY_FEE
            event_data["total_cost"] += TWITTER_API_DAILY_FEE
            event_data["last_charge"] = now.isoformat()
            
            # Update user balance
            new_balance = balance - TWITTER_API_DAILY_FEE
            self.payment_system.user_balances[user_id] = new_balance
            self.payment_system.save_user_balances()
            
            self.save_usage_data()
            
            logger.info(f"✓ Charged user {user_id} daily fee: {TWITTER_API_DAILY_FEE} USDC for {event_slug}")
            
            return {
                "charged": True,
                "amount": TWITTER_API_DAILY_FEE,
                "message": f"Daily TwitterAPI.io fee charged: {TWITTER_API_DAILY_FEE} USDC",
                "new_balance": new_balance,
                "signature": transfer_result["signature"]
            }
        else:
            logger.error(f"Failed to charge daily fee for user {user_id}")
            return {
                "charged": False,
                "amount": 0.0,
                "message": "Transfer failed",
                "should_stop": True
            }
    
    def get_usage_summary(self, user_id: int, event_slug: str) -> Dict:
        """Get usage summary for an event"""
        user_id_str = str(user_id)
        
        if user_id_str not in self.usage_data or event_slug not in self.usage_data[user_id_str]:
            return {
                "exists": False,
                "message": "No usage data found"
            }
        
        event_data = self.usage_data[user_id_str][event_slug]
        started = datetime.fromisoformat(event_data["started_at"])
        duration = datetime.utcnow() - started
        
        return {
            "exists": True,
            "started_at": event_data["started_at"],
            "duration_days": duration.days,
            "duration_hours": duration.total_seconds() / 3600,
            "grok_calls": event_data["grok_calls"],
            "total_grok_calls": event_data["total_grok_calls"],
            "total_grok_cost": event_data["total_grok_cost"],
            "twitter_api_days": event_data["twitter_api_days"],
            "twitter_api_cost": event_data["twitter_api_cost"],
            "total_cost": event_data["total_cost"],
            "last_charge": event_data["last_charge"]
        }
    
    def get_user_total_usage(self, user_id: int) -> Dict:
        """Get total usage across all events for a user"""
        user_id_str = str(user_id)
        
        if user_id_str not in self.usage_data:
            return {
                "total_events": 0,
                "total_cost": 0.0,
                "total_grok_calls": 0
            }
        
        total_cost = 0.0
        total_grok_calls = 0
        events = []
        
        for event_slug, event_data in self.usage_data[user_id_str].items():
            total_cost += event_data["total_cost"]
            total_grok_calls += event_data["total_grok_calls"]
            events.append({
                "event": event_slug,
                "cost": event_data["total_cost"],
                "started_at": event_data["started_at"]
            })
        
        return {
            "total_events": len(events),
            "total_cost": total_cost,
            "total_grok_calls": total_grok_calls,
            "events": events
        }


# Singleton instance
usage_billing = None

def get_usage_billing(payment_system):
    """Get or create usage billing instance"""
    global usage_billing
    if usage_billing is None:
        usage_billing = UsageBilling(payment_system)
    return usage_billing
