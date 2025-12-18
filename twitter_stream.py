"""
Twitter Stream Manager

Handles Twitter API v2 Filtered Stream connections.
Responsible for:
- Creating and managing stream rules
- Connecting to Twitter streaming API
- Delivering tweets to the agent
"""

import os
import json
import asyncio
import logging
from typing import Dict, List, Optional, Callable, Set
import aiohttp
from datetime import datetime

logger = logging.getLogger(__name__)

TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")
TWITTER_STREAM_URL = "https://api.twitter.com/2/tweets/search/stream"
TWITTER_RULES_URL = "https://api.twitter.com/2/tweets/search/stream/rules"


class TwitterStream:
    """
    Manages Twitter Filtered Stream API v2.
    
    Each event gets its own stream rule that monitors specific
    accounts and keywords as defined by Grok.
    """
    
    def __init__(self):
        self.bearer_token = TWITTER_BEARER_TOKEN
        self.active_streams: Dict[str, asyncio.Task] = {}  # event_slug -> stream task
        self.tweet_callbacks: Dict[str, Callable] = {}  # event_slug -> callback function
        
    async def _get_headers(self) -> Dict:
        """Get Twitter API headers"""
        return {
            "Authorization": f"Bearer {self.bearer_token}",
            "Content-Type": "application/json"
        }
    
    async def validate_accounts(self, accounts: List[str]) -> List[str]:
        """
        Validate that Twitter accounts exist via API.
        
        Args:
            accounts: List of Twitter handles (with or without @)
            
        Returns:
            List of valid account handles
        """
        if not accounts:
            return []
            
        # Remove @ symbols
        usernames = [acc.lstrip('@') for acc in accounts]
        
        # Twitter API to lookup users
        url = "https://api.twitter.com/2/users/by"
        params = {
            "usernames": ",".join(usernames[:100])  # Max 100 at once
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers=await self._get_headers(),
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        valid_users = data.get('data', [])
                        valid_handles = [f"@{user['username']}" for user in valid_users]
                        logger.info(f"Validated {len(valid_handles)}/{len(accounts)} accounts")
                        return valid_handles
                    else:
                        error = await response.text()
                        logger.error(f"Error validating accounts: {error}")
                        return []
        except Exception as e:
            logger.error(f"Failed to validate accounts: {e}")
            return []
    
    async def create_stream_rule(
        self,
        event_slug: str,
        accounts: List[str],
        keywords: List[str],
        tag: Optional[str] = None
    ) -> bool:
        """
        Create a filtered stream rule for an event.
        
        Twitter Filtered Stream rules use a query language:
        - from:username - tweets from specific account
        - keyword - tweets containing keyword
        - OR - logical OR
        - ( ) - grouping
        
        Example: (from:elonmusk OR bitcoin OR crypto) -is:retweet
        
        Args:
            event_slug: Unique identifier for the event
            accounts: List of Twitter handles to monitor
            keywords: List of keywords to monitor
            tag: Optional tag for the rule (defaults to event_slug)
            
        Returns:
            True if rule created successfully
        """
        if not tag:
            tag = event_slug
            
        # Build Twitter query
        query_parts = []
        
        # Add account filters
        if accounts:
            account_filters = " OR ".join([f"from:{acc.lstrip('@')}" for acc in accounts])
            query_parts.append(f"({account_filters})")
        
        # Add keyword filters
        if keywords:
            # Escape keywords and handle phrases
            keyword_filters = []
            for kw in keywords:
                if " " in kw:
                    # Phrase - use quotes
                    keyword_filters.append(f'"{kw}"')
                else:
                    keyword_filters.append(kw)
            
            keyword_query = " OR ".join(keyword_filters)
            query_parts.append(f"({keyword_query})")
        
        if not query_parts:
            logger.error("Cannot create rule without accounts or keywords")
            return False
        
        # Combine with OR (either from account OR contains keyword)
        # Also exclude retweets and replies for cleaner signal
        full_query = " OR ".join(query_parts) + " -is:retweet -is:reply"
        
        # Twitter has a 512 character limit on rules
        if len(full_query) > 512:
            logger.warning(f"Query too long ({len(full_query)} chars), truncating...")
            full_query = full_query[:509] + "..."
        
        rule_payload = {
            "add": [
                {
                    "value": full_query,
                    "tag": tag
                }
            ]
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    TWITTER_RULES_URL,
                    headers=await self._get_headers(),
                    json=rule_payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status in [200, 201]:
                        data = await response.json()
                        logger.info(f"✓ Created stream rule for {event_slug}")
                        logger.info(f"  Query: {full_query}")
                        return True
                    else:
                        error = await response.text()
                        logger.error(f"Failed to create rule: {error}")
                        return False
        except Exception as e:
            logger.error(f"Error creating stream rule: {e}")
            return False
    
    async def delete_stream_rule(self, event_slug: str) -> bool:
        """Delete stream rule for an event"""
        try:
            # First, get all rules to find the one to delete
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    TWITTER_RULES_URL,
                    headers=await self._get_headers()
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        rules = data.get('data', [])
                        
                        # Find rule with matching tag
                        rule_ids = [r['id'] for r in rules if r.get('tag') == event_slug]
                        
                        if not rule_ids:
                            logger.warning(f"No rule found for {event_slug}")
                            return False
                        
                        # Delete the rule(s)
                        delete_payload = {"delete": {"ids": rule_ids}}
                        
                        async with session.post(
                            TWITTER_RULES_URL,
                            headers=await self._get_headers(),
                            json=delete_payload
                        ) as del_response:
                            if del_response.status == 200:
                                logger.info(f"✓ Deleted stream rule for {event_slug}")
                                return True
                            else:
                                error = await del_response.text()
                                logger.error(f"Failed to delete rule: {error}")
                                return False
        except Exception as e:
            logger.error(f"Error deleting stream rule: {e}")
            return False
    
    async def start_stream(
        self,
        event_slug: str,
        callback: Callable[[Dict], None]
    ):
        """
        Start listening to the Twitter stream for an event.
        
        Args:
            event_slug: Event identifier
            callback: Async function to call with each tweet
                     Receives dict with: {text, author, tweet_id, created_at, ...}
        """
        if event_slug in self.active_streams:
            logger.warning(f"Stream already active for {event_slug}")
            return
        
        self.tweet_callbacks[event_slug] = callback
        
        # Create background task for streaming
        task = asyncio.create_task(self._stream_tweets(event_slug))
        self.active_streams[event_slug] = task
        
        logger.info(f"✓ Started stream for {event_slug}")
    
    async def _stream_tweets(self, event_slug: str):
        """
        Background task that maintains stream connection.
        Auto-reconnects on errors.
        """
        retry_delay = 5
        max_retry_delay = 320  # Max 5+ minutes
        
        while event_slug in self.tweet_callbacks:
            try:
                # Tweet fields to request
                params = {
                    "tweet.fields": "created_at,author_id,public_metrics,entities",
                    "user.fields": "username,verified,public_metrics",
                    "expansions": "author_id"
                }
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        TWITTER_STREAM_URL,
                        headers=await self._get_headers(),
                        params=params,
                        timeout=aiohttp.ClientTimeout(total=None)  # No timeout for stream
                    ) as response:
                        if response.status == 200:
                            logger.info(f"Connected to Twitter stream for {event_slug}")
                            retry_delay = 5  # Reset retry delay on successful connection
                            
                            # Read stream line by line
                            async for line in response.content:
                                if event_slug not in self.tweet_callbacks:
                                    # Stream was stopped
                                    break
                                
                                if not line.strip():
                                    continue  # Skip keep-alive lines
                                
                                try:
                                    tweet_data = json.loads(line)
                                    
                                    # Extract tweet info
                                    if 'data' in tweet_data:
                                        tweet = tweet_data['data']
                                        includes = tweet_data.get('includes', {})
                                        users = {u['id']: u for u in includes.get('users', [])}
                                        
                                        author = users.get(tweet.get('author_id'), {})
                                        
                                        parsed_tweet = {
                                            "tweet_id": tweet.get('id'),
                                            "text": tweet.get('text'),
                                            "author": author.get('username', 'unknown'),
                                            "author_verified": author.get('verified', False),
                                            "author_followers": author.get('public_metrics', {}).get('followers_count', 0),
                                            "created_at": tweet.get('created_at'),
                                            "likes": tweet.get('public_metrics', {}).get('like_count', 0),
                                            "retweets": tweet.get('public_metrics', {}).get('retweet_count', 0),
                                            "event_slug": event_slug,
                                            "received_at": datetime.utcnow().isoformat()
                                        }
                                        
                                        # Call the callback
                                        callback = self.tweet_callbacks.get(event_slug)
                                        if callback:
                                            asyncio.create_task(callback(parsed_tweet))
                                            
                                except json.JSONDecodeError:
                                    logger.error(f"Failed to parse tweet JSON: {line}")
                                except Exception as e:
                                    logger.error(f"Error processing tweet: {e}")
                        else:
                            error = await response.text()
                            logger.error(f"Stream error {response.status}: {error}")
                            
            except asyncio.CancelledError:
                logger.info(f"Stream cancelled for {event_slug}")
                break
            except Exception as e:
                logger.error(f"Stream connection error for {event_slug}: {e}")
            
            # Retry with exponential backoff
            if event_slug in self.tweet_callbacks:
                logger.info(f"Reconnecting stream in {retry_delay}s...")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, max_retry_delay)
    
    async def stop_stream(self, event_slug: str):
        """Stop streaming for an event"""
        if event_slug in self.tweet_callbacks:
            del self.tweet_callbacks[event_slug]
        
        if event_slug in self.active_streams:
            task = self.active_streams[event_slug]
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            del self.active_streams[event_slug]
            logger.info(f"✓ Stopped stream for {event_slug}")
    
    async def get_active_rules(self) -> List[Dict]:
        """Get all active stream rules"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    TWITTER_RULES_URL,
                    headers=await self._get_headers()
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get('data', [])
                    else:
                        return []
        except Exception as e:
            logger.error(f"Error getting rules: {e}")
            return []


# Singleton instance
twitter_stream = TwitterStream()
