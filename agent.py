"""
Agent Executor - The Mechanical Executor

The agent has NO independent decision-making capability.
It simply:
1. Applies Grok's rules mechanically
2. Fetches tweets via Twitter API
3. Routes intelligence to users
4. Reports performance metrics back to Grok

Grok = Brain (makes all decisions)
Agent = Hands (executes decisions)
"""

import os
import json
import asyncio
import logging
from typing import Dict, List, Optional, Set
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, asdict

from grok_engine import grok_engine
from twitter_stream import twitter_stream
from twitter_twitterapio import TwitterApiIO
from payment_system import PaymentSystem
from usage_billing import get_usage_billing

logger = logging.getLogger(__name__)

AGENTS_FILE = "agents.json"
INTELLIGENCE_FILE = "intelligence.json"


@dataclass
class EventAgent:
    """Represents an agent instance for a specific event"""
    event_slug: str
    event_question: str
    event_description: str
    category: str
    ruleset: Dict
    subscribers: List[int]  # Telegram user IDs
    created_at: str
    status: str  # "setup", "active", "paused", "stopped"
    
    # Performance metrics
    total_tweets: int = 0
    relevant_tweets: int = 0
    high_priority_tweets: int = 0
    last_refinement: Optional[str] = None
    
    def to_dict(self):
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict):
        return cls(**data)


class AgentManager:
    """
    Manages all event agents.
    Each agent monitors one Polymarket event.
    """
    
    def __init__(self):
        self.agents: Dict[str, EventAgent] = {}  # event_slug -> agent
        self.intelligence_db: Dict[str, List[Dict]] = {}  # event_slug -> [analyzed tweets]
        self.performance_metrics: Dict[str, Dict] = {}  # event_slug -> metrics
        
        self.load_agents()
        self.load_intelligence()
        
        # Scheduled tasks
        self.refinement_tasks: Dict[str, asyncio.Task] = {}
        self.digest_tasks: Dict[str, asyncio.Task] = {}
        
        # TwitterAPI.io WebSocket client (shared across all agents)
        self.twitter_client = None
        self.websocket_started = False
        
        # Usage billing system
        self.payment_system = PaymentSystem()
        self.usage_billing = get_usage_billing(self.payment_system)    
    def load_agents(self):
        """Load saved agents from disk"""
        if Path(AGENTS_FILE).exists():
            try:
                with open(AGENTS_FILE, 'r') as f:
                    data = json.load(f)
                    for event_slug, agent_data in data.items():
                        self.agents[event_slug] = EventAgent.from_dict(agent_data)
                logger.info(f"Loaded {len(self.agents)} agents")
            except Exception as e:
                logger.error(f"Error loading agents: {e}")
    
    def save_agents(self):
        """Save agents to disk"""
        try:
            data = {slug: agent.to_dict() for slug, agent in self.agents.items()}
            with open(AGENTS_FILE, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving agents: {e}")
    
    def load_intelligence(self):
        """Load intelligence database"""
        if Path(INTELLIGENCE_FILE).exists():
            try:
                with open(INTELLIGENCE_FILE, 'r') as f:
                    self.intelligence_db = json.load(f)
                logger.info(f"Loaded intelligence for {len(self.intelligence_db)} events")
            except Exception as e:
                logger.error(f"Error loading intelligence: {e}")
    
    def save_intelligence(self):
        """Save intelligence to disk"""
        try:
            # Only keep last 1000 tweets per event to manage size
            trimmed_db = {}
            for event_slug, tweets in self.intelligence_db.items():
                trimmed_db[event_slug] = tweets[-1000:]
            
            with open(INTELLIGENCE_FILE, 'w') as f:
                json.dump(trimmed_db, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving intelligence: {e}")
    
    async def create_agent(
        self,
        event_slug: str,
        event_question: str,
        event_description: str,
        category: str,
        initial_subscriber: int
    ) -> Optional[EventAgent]:
        """
        Create a new agent for an event.
        
        Steps:
        0. Fetch historical context from Polymarket's Grok API (existing infra)
        1. Ask xAI Grok to generate initial ruleset with historical context
        2. Validate Twitter accounts
        3. Create Twitter stream rule
        4. Spawn agent instance
        5. Return agent details
        """
        logger.info(f"Creating agent for {event_slug}")
        
        # Step 0: Get historical baseline from Polymarket's existing Grok API
        logger.info("Fetching historical Market Context from Polymarket...")
        historical_context = await PolymarketAPI.fetch_market_context(event_slug)
        if not historical_context:
            logger.warning("No historical context available from Polymarket")
            historical_context = "No historical context available."
        else:
            logger.info(f"Got historical context ({len(historical_context)} chars)")
        
        # Step 0.5: Backfill recent tweets using Advanced Search
        logger.info("Backfilling recent tweets via Advanced Search...")
        recent_tweets_context = ""
        try:
            twitter_client = TwitterApiIO()
            
            # Extract keywords from event for initial search
            # Basic keyword extraction from question and description
            import re
            words = re.findall(r'\b[A-Z][a-z]+\b|\b[A-Z]{2,}\b', event_question + " " + event_description)
            keywords = list(set([w for w in words if len(w) > 3]))[:5]  # Top 5 unique keywords
            
            if keywords:
                backfill_result = await asyncio.to_thread(
                    twitter_client.backfill_recent_tweets,
                    keywords=keywords,
                    accounts=[],  # No accounts yet, Grok will suggest them
                    hours_back=48,
                    max_results=50
                )
                
                recent_tweets_context = twitter_client.format_for_grok(backfill_result['tweets'])
                logger.info(f"Backfilled {backfill_result['total_fetched']} recent tweets")
            else:
                logger.warning("Could not extract keywords for backfill")
                
        except Exception as e:
            logger.error(f"Advanced Search backfill failed: {e}")
            recent_tweets_context = "No recent tweets available."
        
        # Step 1: xAI Grok generates forward monitoring ruleset
        logger.info("Asking xAI Grok to generate monitoring rules...")
        ruleset = await grok_engine.generate_initial_ruleset(
            event_slug=event_slug,
            event_question=event_question,
            event_description=event_description,
            category=category,
            historical_context=historical_context,
            recent_tweets=recent_tweets_context
        )
        
        if not ruleset:
            logger.error("Failed to generate ruleset")
            return None
        
        # Step 2: Setup TwitterAPI.io monitoring
        accounts = ruleset.get('accounts', [])[:5]  # Limit to top 5 priority accounts
        
        if not accounts:
            logger.error("No accounts identified by Grok - cannot create agent")
            return None
        
        # Initialize Twitter client if not already done
        if not self.twitter_client:
            self.twitter_client = TwitterApiIO()
        
        # Step 3: Add accounts to monitoring
        logger.info(f"Adding {len(accounts)} accounts to Twitter monitoring...")
        monitor_result = await asyncio.to_thread(
            self.twitter_client.add_multiple_users_to_monitor,
            accounts
        )
        
        if monitor_result['total_added'] == 0:
            logger.error("Failed to add any accounts to monitoring")
            return None
        
        logger.info(f"✓ Added {monitor_result['total_added']} accounts to monitoring")
        
        # Update ruleset with successfully added accounts
        ruleset['accounts'] = monitor_result['successful']
        
        # Step 4: Start WebSocket if not already running
        if not self.websocket_started:
            logger.info("Starting WebSocket stream...")
            self.twitter_client.start_websocket_stream(self._websocket_tweet_handler)
            self.websocket_started = True
            logger.info("✓ WebSocket stream started")
        
        # Step 5: Create agent instance
        agent = EventAgent(
            event_slug=event_slug,
            event_question=event_question,
            event_description=event_description,
            category=category,
            ruleset=ruleset,
            subscribers=[initial_subscriber],
            created_at=datetime.utcnow().isoformat(),
            status="setup"  # Will become "active" after payment
        )
        
        self.agents[event_slug] = agent
        self.intelligence_db[event_slug] = []
        self.performance_metrics[event_slug] = self._init_metrics()
        
        # Initialize usage billing tracking for this event
        self.usage_billing.init_event_tracking(initial_subscriber, event_slug)
        logger.info(f"✓ Initialized usage billing for {event_slug}")
        
        self.save_agents()
        
        logger.info(f"✓ Agent created for {event_slug}")
        return agent
    
    def _init_metrics(self) -> Dict:
        """Initialize performance metrics for an event"""
        return {
            "total_tweets": 0,
            "relevant_tweets": 0,
            "high_priority_tweets": 0,
            "avg_relevance_score": 0.0,
            "avg_credibility_score": 0.0,
            "account_performance": {},
            "keyword_performance": {},
            "user_engagement": {"delivered": 0, "clicks": 0},
            "budget_used": {"account_monitoring": 0.0, "keyword_search": 0.0},
            "start_time": datetime.utcnow().isoformat()
        }
    
    async def start_agent(self, event_slug: str):
        """
        Start an agent (after payment received).
        
        1. WebSocket is already streaming (shared connection)
        2. Begin processing tweets when they arrive
        3. Schedule hourly digests
        4. Schedule 6-hour refinements
        5. Schedule daily TwitterAPI.io fee checks
        """
        agent = self.agents.get(event_slug)
        if not agent:
            logger.error(f"No agent found for {event_slug}")
            return
        
        # Update status
        agent.status = "active"
        self.save_agents()
        
        # WebSocket is already running (shared connection)
        logger.info(f"Agent {event_slug} is now active and receiving tweets via WebSocket")
        
        # Schedule hourly digest
        digest_task = asyncio.create_task(self._digest_scheduler(event_slug))
        self.digest_tasks[event_slug] = digest_task
        
        # Schedule 6-hour refinement
        refinement_task = asyncio.create_task(self._refinement_scheduler(event_slug))
        self.refinement_tasks[event_slug] = refinement_task
        
        # Schedule daily TwitterAPI.io fee check
        daily_fee_task = asyncio.create_task(self._daily_fee_scheduler(event_slug))
        if not hasattr(self, 'daily_fee_tasks'):
            self.daily_fee_tasks = {}
        self.daily_fee_tasks[event_slug] = daily_fee_task
        
        logger.info(f"✓ Agent started for {event_slug}")
    
    def _websocket_tweet_handler(self, data: Dict):
        """
        WebSocket callback - routes tweets to appropriate agent.
        This runs synchronously in WebSocket thread.
        """
        try:
            tweets = data.get('tweets', [])
            
            # Check each tweet's author to determine which agent should process it
            for tweet in tweets:
                author_username = tweet.get('author', {}).get('userName', '').lower()
                
                # Find which agent(s) are monitoring this author
                for event_slug, agent in self.agents.items():
                    if agent.status != "active":
                        continue
                    
                    monitored_accounts = [acc.lower() for acc in agent.ruleset.get('accounts', [])]
                    
                    if author_username in monitored_accounts:
                        # This agent is monitoring this account
                        # Convert to async handling
                        asyncio.create_task(self._handle_tweet(event_slug, tweet))
                        
        except Exception as e:
            logger.error(f"Error in WebSocket tweet handler: {e}")
    
    async def _handle_tweet(self, event_slug: str, tweet: Dict):
        """
        Process incoming tweet using Grok's rules - EFFICIENTLY.
        
        PRIORITY SYSTEM:
        1. Check if tweet matches Grok's "priority_nodes" (high-weight developments)
        2. If priority node → IMMEDIATE Grok analysis + delivery (bypass all filters)
        3. Else → Pre-filter with heuristics
        4. If passes pre-filter → Grok analysis
        5. Store intelligence & deliver based on priority
        
        Priority nodes are momentous developments Grok identifies as critical.
        """
        agent = self.agents.get(event_slug)
        if not agent or agent.status != "active":
            return
        
        # Update metrics
        metrics = self.performance_metrics.get(event_slug, {})
        metrics["total_tweets"] = metrics.get("total_tweets", 0) + 1
        
        # Extract info from TwitterAPI.io format
        author_data = tweet.get('author', {})
        author_username = author_data.get('userName', 'unknown')
        tweet_text = tweet.get('text', '')
        
        # PRIORITY CHECK: Does this match a critical node Grok identified?
        is_priority_node, priority_reason = self._check_priority_node(tweet, agent)
        
        if is_priority_node:
            # CRITICAL DEVELOPMENT - Bypass all filters, immediate Grok analysis
            logger.warning(f"🚨 PRIORITY NODE triggered: @{author_username} - {priority_reason}")
            
            # Check balance for ALL subscribers before making Grok call
            for subscriber_id in agent.subscribers:
                billing_result = await self.usage_billing.record_grok_call(
                    subscriber_id, event_slug, "analyze_tweet_priority"
                )
                
                if not billing_result.get("success"):
                    # Insufficient balance - pause monitoring for this user
                    logger.warning(f"⚠️ User {subscriber_id} low balance: {billing_result.get('message')}")
                    await self._notify_low_balance_and_pause(subscriber_id, event_slug, billing_result)
                    # Remove from subscribers list
                    agent.subscribers.discard(subscriber_id)
            
            # If no subscribers left with sufficient balance, skip analysis
            if not agent.subscribers:
                logger.warning(f"No subscribers with sufficient balance for {event_slug}. Skipping Grok call.")
                return
            
            # Immediate Grok analysis
            analysis = await grok_engine.analyze_tweet(
                tweet_text=tweet_text,
                tweet_author=author_username,
                event_question=agent.event_question,
                ruleset=agent.ruleset
            )
            
            if analysis:
                # Force high priority for immediate delivery
                analysis['priority'] = 'high'
                analysis['priority_node_reason'] = priority_reason
                
                # Store and deliver immediately
                intelligence = {
                    **tweet,
                    **analysis,
                    "analyzed_at": datetime.utcnow().isoformat(),
                    "is_priority_node": True
                }
                
                self.intelligence_db[event_slug].append(intelligence)
                metrics["high_priority_tweets"] = metrics.get("high_priority_tweets", 0) + 1
                
                # IMMEDIATE delivery to user
                await self._deliver_intelligence(event_slug, intelligence)
                
                logger.warning(f"✓ Priority node delivered immediately")
                return
        
        # Not a priority node - use normal pre-filter
        # PRE-FILTER: Skip obvious low-value tweets BEFORE calling Grok
        # This saves 80-90% of Grok API calls
        if self._should_skip_tweet(tweet, agent):
            logger.debug(f"Tweet from @{author_username} pre-filtered out (low engagement/quality)")
            return
        
        # Passed pre-filter - check balance for ALL subscribers before making Grok call
        for subscriber_id in agent.subscribers:
            billing_result = await self.usage_billing.record_grok_call(
                subscriber_id, event_slug, "analyze_tweet"
            )
            
            if not billing_result.get("success"):
                # Insufficient balance - pause monitoring for this user
                logger.warning(f"⚠️ User {subscriber_id} low balance: {billing_result.get('message')}")
                await self._notify_low_balance_and_pause(subscriber_id, event_slug, billing_result)
                # Remove from subscribers list
                agent.subscribers.discard(subscriber_id)
        
        # If no subscribers left with sufficient balance, skip analysis
        if not agent.subscribers:
            logger.warning(f"No subscribers with sufficient balance for {event_slug}. Skipping Grok call.")
            return
        
        # Now get Grok's analysis
        logger.info(f"Analyzing tweet from @{author_username} for {event_slug}")
        
        analysis = await grok_engine.analyze_tweet(
            tweet_text=tweet_text,
            tweet_author=author_username,
            event_question=agent.event_question,
            ruleset=agent.ruleset
        )
        
        if not analysis:
            logger.warning("Failed to get Grok analysis")
            return
        
        # Apply Grok's filters
        filters = agent.ruleset.get('filters', {})
        relevance_threshold = filters.get('relevance_threshold', 0.7)
        credibility_threshold = filters.get('credibility_threshold', 0.6)
        
        if not analysis.get('relevant', False):
            logger.info("Tweet not relevant, skipping")
            return
        
        if analysis.get('relevance_score', 0) < relevance_threshold:
            logger.info(f"Relevance score too low: {analysis.get('relevance_score')}")
            return
        
        if analysis.get('credibility_score', 0) < credibility_threshold:
            logger.info(f"Credibility score too low: {analysis.get('credibility_score')}")
            return
        
        # Passes all filters - store intelligence
        intelligence = {
            **tweet,
            **analysis,
            "analyzed_at": datetime.utcnow().isoformat()
        }
        
        self.intelligence_db[event_slug].append(intelligence)
        
        # Update metrics
        metrics["relevant_tweets"] = metrics.get("relevant_tweets", 0) + 1
        if analysis.get('priority') == 'high':
            metrics["high_priority_tweets"] = metrics.get("high_priority_tweets", 0) + 1
        
        # Update rolling averages
        total_relevant = metrics["relevant_tweets"]
        metrics["avg_relevance_score"] = (
            (metrics.get("avg_relevance_score", 0) * (total_relevant - 1) + 
             analysis.get('relevance_score', 0)) / total_relevant
        )
        metrics["avg_credibility_score"] = (
            (metrics.get("avg_credibility_score", 0) * (total_relevant - 1) + 
             analysis.get('credibility_score', 0)) / total_relevant
        )
        
        # Track account performance
        author = tweet['author']
        if author not in metrics.get("account_performance", {}):
            metrics.setdefault("account_performance", {})[author] = {
                "tweets": 0,
                "avg_relevance": 0.0
            }
        
        account_stats = metrics["account_performance"][author]
        account_stats["tweets"] += 1
        account_stats["avg_relevance"] = (
            (account_stats["avg_relevance"] * (account_stats["tweets"] - 1) +
             analysis.get('relevance_score', 0)) / account_stats["tweets"]
        )
        
        self.save_intelligence()
        
        # Deliver based on priority
        await self._deliver_intelligence(event_slug, intelligence)
        
        logger.info(f"✓ Processed tweet: Priority={analysis.get('priority')}, Sentiment={analysis.get('sentiment')}")
    
    def _check_priority_node(self, tweet: Dict, agent: EventAgent) -> tuple[bool, str]:
        """
        Check if tweet matches any of Grok's priority nodes.
        Priority nodes are high-weight developments that bypass all filters.
        
        Returns: (is_priority, reason)
        """
        priority_nodes = agent.ruleset.get('priority_nodes', [])
        if not priority_nodes:
            return (False, "")
        
        author_data = tweet.get('author', {})
        author_username = author_data.get('userName', '').lower().lstrip('@')
        tweet_text = tweet.get('text', '').lower()
        is_verified = author_data.get('isBlueVerified', False)
        followers = author_data.get('followers', 0)
        
        for node in priority_nodes:
            node_type = node.get('type')
            
            # Type 1: Specific account tweeting specific keywords
            if node_type == 'account_specific':
                target_account = node.get('account', '').lower().lstrip('@')
                keywords = [kw.lower() for kw in node.get('keywords', [])]
                
                if author_username == target_account:
                    if any(kw in tweet_text for kw in keywords):
                        return (True, node.get('reason', 'Priority account + keyword match'))
            
            # Type 2: Any tweet from critical account
            elif node_type == 'account_any':
                target_account = node.get('account', '').lower().lstrip('@')
                
                if author_username == target_account:
                    return (True, node.get('reason', 'Critical account activity'))
            
            # Type 3: Critical keywords from qualified accounts
            elif node_type == 'keyword_critical':
                keywords = [kw.lower() for kw in node.get('keywords', [])]
                min_followers = node.get('min_followers', 0)
                
                if followers >= min_followers:
                    if any(kw in tweet_text for kw in keywords):
                        return (True, node.get('reason', 'Critical keyword detected'))
            
            # Type 4: Breaking news from verified sources
            elif node_type == 'breaking_news':
                keywords = [kw.lower() for kw in node.get('keywords', [])]
                verified_only = node.get('verified_only', True)
                
                if not verified_only or is_verified:
                    if any(kw in tweet_text for kw in keywords):
                        return (True, node.get('reason', 'Breaking news alert'))
        
        return (False, "")
    
    def _should_skip_tweet(self, tweet: Dict, agent: EventAgent) -> bool:
        """
        Pre-filter tweets BEFORE calling Grok API.
        Returns True if tweet should be skipped (low value).
        
        This is a DUMB filter - just basic heuristics to avoid
        wasting Grok API calls on obviously irrelevant tweets.
        Saves ~80-90% of API calls.
        """
        author_data = tweet.get('author', {})
        
        # Skip if author is a known bot
        if author_data.get('isAutomated', False):
            return True
        
        # Skip if author has very low followers (likely spam)
        followers = author_data.get('followers', 0)
        if followers < 100:
            return True
        
        # Skip if tweet has zero engagement
        engagement = (
            tweet.get('likeCount', 0) + 
            tweet.get('retweetCount', 0) + 
            tweet.get('replyCount', 0)
        )
        if engagement == 0 and followers < 10000:
            # New tweet from small account - might be valuable, let Grok decide
            # But if it's from tiny account with no engagement, skip
            return False
        
        # Skip retweets unless from verified/high-follower accounts
        if tweet.get('retweeted_tweet') and followers < 50000:
            return True
        
        # Skip replies unless from verified/high-follower accounts
        if tweet.get('isReply', False) and not author_data.get('isBlueVerified', False) and followers < 10000:
            return True
        
        # Passed all basic filters - send to Grok for real analysis
        return False
    
    async def _deliver_intelligence(self, event_slug: str, intelligence: Dict):
        """
        Deliver intelligence to subscribers based on priority.
        
        High priority: Immediate delivery
        Medium priority: Batch with next digest
        Low priority: Include in digest only
        """
        priority = intelligence.get('priority', 'low')
        
        if priority == 'high':
            # Immediate delivery
            await self._send_to_subscribers(event_slug, intelligence, immediate=True)
        # Medium and low will be included in hourly digest
    
    async def _send_to_subscribers(
        self,
        event_slug: str,
        intelligence: Dict,
        immediate: bool = False
    ):
        """
        Send intelligence to subscribers via Telegram.
        This will be implemented in bot.py integration.
        """
        # Placeholder - will be integrated with Telegram bot
        agent = self.agents.get(event_slug)
        if not agent:
            return
        
        logger.info(f"Would send to {len(agent.subscribers)} subscribers")
        # TODO: Integrate with bot.py to actually send messages
    
    async def _digest_scheduler(self, event_slug: str):
        """Run hourly digest synthesis"""
        while event_slug in self.agents and self.agents[event_slug].status == "active":
            try:
                await asyncio.sleep(3600)  # 1 hour
                await self._generate_hourly_digest(event_slug)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in digest scheduler: {e}")
    
    async def _generate_hourly_digest(self, event_slug: str):
        """Generate and deliver hourly digest"""
        agent = self.agents.get(event_slug)
        if not agent:
            return
        
        # Get past hour's intelligence
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        recent_intelligence = [
            intel for intel in self.intelligence_db.get(event_slug, [])
            if datetime.fromisoformat(intel['analyzed_at']) > one_hour_ago
        ]
        
        if not recent_intelligence:
            logger.info(f"No intelligence to synthesize for {event_slug}")
            return
        
        logger.info(f"Synthesizing digest from {len(recent_intelligence)} tweets...")
        
        # Check balance for ALL subscribers before making Grok call
        for subscriber_id in agent.subscribers:
            billing_result = await self.usage_billing.record_grok_call(
                subscriber_id, event_slug, "synthesize_digest"
            )
            
            if not billing_result.get("success"):
                # Insufficient balance - pause monitoring for this user
                logger.warning(f"⚠️ User {subscriber_id} low balance: {billing_result.get('message')}")
                await self._notify_low_balance_and_pause(subscriber_id, event_slug, billing_result)
                # Remove from subscribers list
                agent.subscribers.discard(subscriber_id)
        
        # If no subscribers left with sufficient balance, skip digest
        if not agent.subscribers:
            logger.warning(f"No subscribers with sufficient balance for {event_slug}. Skipping digest.")
            return
        
        digest = await grok_engine.synthesize_hourly_digest(
            event_question=agent.event_question,
            analyzed_tweets=recent_intelligence
        )
        
        if digest:
            # Send digest to all subscribers
            logger.info(f"Generated hourly digest for {event_slug}")
            # TODO: Send via Telegram
    
    async def _refinement_scheduler(self, event_slug: str):
        """Run 6-hour rule refinement"""
        while event_slug in self.agents and self.agents[event_slug].status == "active":
            try:
                await asyncio.sleep(21600)  # 6 hours
                await self._refine_rules(event_slug)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in refinement scheduler: {e}")
    
    async def _daily_fee_scheduler(self, event_slug: str):
        """Check and charge daily TwitterAPI.io fee every 24 hours"""
        agent = self.agents.get(event_slug)
        if not agent:
            return
            
        while event_slug in self.agents and self.agents[event_slug].status == "active":
            try:
                await asyncio.sleep(86400)  # 24 hours
                
                # Check and charge fee for all subscribers
                subscribers_to_remove = []
                for subscriber_id in list(agent.subscribers):  # Copy to avoid modification during iteration
                    result = await self.usage_billing.check_and_charge_daily_fee(
                        subscriber_id, 
                        event_slug
                    )
                    
                    if result.get('should_stop'):
                        # Insufficient balance - pause monitoring for this user
                        logger.warning(f"⚠️ User {subscriber_id} low balance: {result['message']}")
                        await self._notify_low_balance_and_pause(subscriber_id, event_slug, result)
                        subscribers_to_remove.append(subscriber_id)
                    elif result.get('charged'):
                        logger.info(f"✓ Charged daily fee for user {subscriber_id}: ${result['amount']:.2f}")
                        
                        # Send low balance warning if present
                        if result.get('warning'):
                            logger.info(f"💡 Low balance warning for user {subscriber_id}")
                            # TODO: Send warning via Telegram
                            print(f"\n{'='*60}")
                            print(f"LOW BALANCE WARNING TO USER {subscriber_id}:")
                            print(result['warning'])
                            print(f"{'='*60}\n")
                    else:
                        logger.warning(f"Failed to charge daily fee for user {subscriber_id}: {result.get('message', 'Unknown error')}")
                
                # Remove subscribers with insufficient balance
                for subscriber_id in subscribers_to_remove:
                    agent.subscribers.discard(subscriber_id)
                
                # If no subscribers left, stop the agent
                if not agent.subscribers:
                    logger.warning(f"No subscribers left for {event_slug}. Stopping agent.")
                    await self.stop_agent(event_slug)
                    break
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in daily fee scheduler: {e}")
    
    async def _refine_rules(self, event_slug: str):
        """Refine monitoring rules based on performance"""
        agent = self.agents.get(event_slug)
        if not agent:
            return
        
        metrics = self.performance_metrics.get(event_slug, {})
        
        logger.info(f"Refining rules for {event_slug}...")
        logger.info(f"  Performance: {metrics.get('relevant_tweets')}/{metrics.get('total_tweets')} relevant")
        
        # Check balance for ALL subscribers before making Grok call
        for subscriber_id in agent.subscribers:
            billing_result = await self.usage_billing.record_grok_call(
                subscriber_id, event_slug, "refine_ruleset"
            )
            
            if not billing_result.get("success"):
                # Insufficient balance - pause monitoring for this user
                logger.warning(f"⚠️ User {subscriber_id} low balance: {billing_result.get('message')}")
                await self._notify_low_balance_and_pause(subscriber_id, event_slug, billing_result)
                # Remove from subscribers list
                agent.subscribers.discard(subscriber_id)
        
        # If no subscribers left with sufficient balance, skip refinement
        if not agent.subscribers:
            logger.warning(f"No subscribers with sufficient balance for {event_slug}. Skipping refinement.")
            return
        
        refined_ruleset = await grok_engine.refine_ruleset(
            event_slug=event_slug,
            current_ruleset=agent.ruleset,
            performance_metrics=metrics
        )
        
        if refined_ruleset:
            # Update agent ruleset
            old_ruleset = agent.ruleset
            agent.ruleset = refined_ruleset
            agent.last_refinement = datetime.utcnow().isoformat()
            
            # Check if accounts changed
            old_accounts = set(old_ruleset.get('accounts', []))
            new_accounts = set(refined_ruleset.get('accounts', []))
            
            if old_accounts != new_accounts:
                # Update Twitter user monitoring
                logger.info("Accounts changed, updating user monitoring...")
                
                # Remove old accounts that are no longer needed
                accounts_to_remove = old_accounts - new_accounts
                if accounts_to_remove:
                    await asyncio.to_thread(
                        self.twitter_client.remove_multiple_users_from_monitor,
                        list(accounts_to_remove)
                    )
                
                # Add new accounts
                accounts_to_add = new_accounts - old_accounts
                if accounts_to_add:
                    await asyncio.to_thread(
                        self.twitter_client.add_multiple_users_to_monitor,
                        list(accounts_to_add)
                    )
            
            # Reset metrics for next cycle
            self.performance_metrics[event_slug] = self._init_metrics()
            
            self.save_agents()
            logger.info(f"✓ Rules refined for {event_slug}")
    
    async def _notify_low_balance_and_pause(self, user_id: int, event_slug: str, billing_result: Dict):
        """
        Notify user about low balance and pause their monitoring.
        
        Args:
            user_id: The user's Telegram ID
            event_slug: The event being monitored
            billing_result: Result from record_grok_call() with balance info
        """
        balance = billing_result.get("balance", 0.0)
        message = billing_result.get("message", "Insufficient balance")
        
        # Get event details for notification
        agent = self.agents.get(event_slug)
        event_question = agent.event_question if agent else event_slug
        
        # Send Telegram notification (this will be handled by bot.py)
        notification = (
            f"⚠️ *MONITORING PAUSED*\n\n"
            f"Your monitoring for:\n"
            f"_{event_question}_\n\n"
            f"has been paused due to low balance.\n\n"
            f"💰 Current Balance: ${balance:.2f} USDC\n\n"
            f"{message}\n\n"
            f"To resume monitoring:\n"
            f"1️⃣ Deposit USDC: /deposit\n"
            f"2️⃣ Check balance: /balance\n"
            f"3️⃣ Restart monitoring: /watch"
        )
        
        logger.info(f"📢 Low balance notification for user {user_id}: ${balance:.2f}")
        
        # TODO: Send via bot.py telegram integration
        # For now, just log it
        print(f"\n{'='*60}")
        print(f"NOTIFICATION TO USER {user_id}:")
        print(notification)
        print(f"{'='*60}\n")
        
        # Remove user from all monitoring for this event
        await self.remove_subscriber(event_slug, user_id)
    
    async def stop_agent(self, event_slug: str):
        """Stop an agent"""
        if event_slug not in self.agents:
            return
        
        agent = self.agents[event_slug]
        
        # Update status
        agent.status = "stopped"
        
        # Remove monitored accounts
        accounts = agent.ruleset.get('accounts', [])
        if accounts and self.twitter_client:
            logger.info(f"Removing {len(accounts)} accounts from monitoring...")
            await asyncio.to_thread(
                self.twitter_client.remove_multiple_users_from_monitor,
                accounts
            )
        
        # Cancel scheduled tasks
        if event_slug in self.digest_tasks:
            self.digest_tasks[event_slug].cancel()
            del self.digest_tasks[event_slug]
        
        if event_slug in self.refinement_tasks:
            self.refinement_tasks[event_slug].cancel()
            del self.refinement_tasks[event_slug]
        
        if hasattr(self, 'daily_fee_tasks') and event_slug in self.daily_fee_tasks:
            self.daily_fee_tasks[event_slug].cancel()
            del self.daily_fee_tasks[event_slug]
        
        # Delete stream rule
        await twitter_stream.delete_stream_rule(event_slug)
        
        self.save_agents()
        logger.info(f"✓ Agent stopped for {event_slug}")
    
    def add_subscriber(self, event_slug: str, user_id: int) -> bool:
        """Add a subscriber to an event"""
        agent = self.agents.get(event_slug)
        if not agent:
            return False
        
        if user_id not in agent.subscribers:
            agent.subscribers.append(user_id)
            self.save_agents()
        
        return True
    
    def remove_subscriber(self, event_slug: str, user_id: int) -> bool:
        """Remove a subscriber from an event"""
        agent = self.agents.get(event_slug)
        if not agent:
            return False
        
        if user_id in agent.subscribers:
            agent.subscribers.remove(user_id)
            self.save_agents()
            
            # If no more subscribers, stop agent
            if not agent.subscribers:
                asyncio.create_task(self.stop_agent(event_slug))
        
        return True


# Singleton instance
agent_manager = AgentManager()
