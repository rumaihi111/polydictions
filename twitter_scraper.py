"""
Twitter Scraper - Active Tweet Search

Alternative to Filtered Streams for when you want to:
- Search historical tweets
- Scrape specific accounts on-demand
- Get tweets from before stream started

Uses Twitter API v2 search endpoints based on Grok's plan.
"""

import os
import logging
from typing import Dict, List, Optional
import aiohttp
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")
TWITTER_SEARCH_URL = "https://api.twitter.com/2/tweets/search/recent"


class TwitterScraper:
    """
    Active scraping based on Grok's monitoring plan.
    Complements the real-time stream.
    """
    
    def __init__(self):
        self.bearer_token = TWITTER_BEARER_TOKEN
    
    async def scrape_by_grok_plan(
        self,
        ruleset: Dict,
        hours_back: int = 24,
        max_results: int = 100
    ) -> List[Dict]:
        """
        Scrape tweets based on Grok's generated plan.
        
        Args:
            ruleset: Grok's monitoring rules
            hours_back: How far back to search
            max_results: Max tweets to return
            
        Returns:
            List of tweets matching Grok's criteria
        """
        accounts = ruleset.get('accounts', [])
        keywords = ruleset.get('keywords', [])
        
        # Build Twitter search query from Grok's plan
        query_parts = []
        
        # Add account filters
        if accounts:
            account_query = " OR ".join([f"from:{acc.lstrip('@')}" for acc in accounts])
            query_parts.append(f"({account_query})")
        
        # Add keyword filters
        if keywords:
            keyword_query = " OR ".join(keywords)
            query_parts.append(f"({keyword_query})")
        
        # Combine with AND/OR logic
        if len(query_parts) == 2:
            # Either from these accounts OR containing these keywords
            query = f"{query_parts[0]} OR {query_parts[1]}"
        elif query_parts:
            query = query_parts[0]
        else:
            logger.error("No search criteria in ruleset")
            return []
        
        # Add filters
        query += " -is:retweet -is:reply lang:en"
        
        # Time range
        start_time = (datetime.utcnow() - timedelta(hours=hours_back)).isoformat() + "Z"
        
        headers = {
            "Authorization": f"Bearer {self.bearer_token}",
            "Content-Type": "application/json"
        }
        
        params = {
            "query": query,
            "start_time": start_time,
            "max_results": min(max_results, 100),  # API limit
            "tweet.fields": "created_at,author_id,public_metrics,entities",
            "user.fields": "username,verified,public_metrics",
            "expansions": "author_id"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    TWITTER_SEARCH_URL,
                    headers=headers,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        tweets = self._parse_tweets(data)
                        logger.info(f"Scraped {len(tweets)} tweets using Grok's plan")
                        return tweets
                    else:
                        error = await response.text()
                        logger.error(f"Twitter search failed: {error}")
                        return []
        except Exception as e:
            logger.error(f"Error scraping tweets: {e}")
            return []
    
    def _parse_tweets(self, data: Dict) -> List[Dict]:
        """Parse Twitter API response into our format"""
        tweets = []
        
        tweet_data = data.get('data', [])
        includes = data.get('includes', {})
        users = {u['id']: u for u in includes.get('users', [])}
        
        for tweet in tweet_data:
            author = users.get(tweet.get('author_id'), {})
            
            parsed = {
                "tweet_id": tweet.get('id'),
                "text": tweet.get('text'),
                "author": author.get('username', 'unknown'),
                "author_verified": author.get('verified', False),
                "author_followers": author.get('public_metrics', {}).get('followers_count', 0),
                "created_at": tweet.get('created_at'),
                "likes": tweet.get('public_metrics', {}).get('like_count', 0),
                "retweets": tweet.get('public_metrics', {}).get('retweet_count', 0),
                "scraped_at": datetime.utcnow().isoformat()
            }
            tweets.append(parsed)
        
        return tweets
    
    async def scrape_account_timeline(
        self,
        account: str,
        max_results: int = 50
    ) -> List[Dict]:
        """
        Scrape recent tweets from a specific account.
        Useful when Grok identifies a key account to monitor.
        """
        # This would use the user timeline endpoint
        # Requires different API endpoint and permissions
        logger.info(f"Would scrape timeline for {account}")
        return []


# Integration with Agent
async def backfill_historical_tweets(agent, hours_back: int = 24):
    """
    After Grok creates a plan, scrape historical tweets
    to get immediate context before stream starts.
    
    Call this in agent.py after creating ruleset.
    """
    scraper = TwitterScraper()
    
    # Get historical tweets using Grok's plan
    historical_tweets = await scraper.scrape_by_grok_plan(
        ruleset=agent.ruleset,
        hours_back=hours_back
    )
    
    # Process each historical tweet through Grok
    from grok_engine import grok_engine
    
    for tweet in historical_tweets:
        analysis = await grok_engine.analyze_tweet(
            tweet_text=tweet['text'],
            tweet_author=tweet['author'],
            event_question=agent.event_question,
            ruleset=agent.ruleset
        )
        
        if analysis and analysis.get('relevant'):
            # Store as intelligence
            intelligence = {**tweet, **analysis}
            # agent.intelligence_db[agent.event_slug].append(intelligence)
            logger.info(f"Backfilled historical intelligence from @{tweet['author']}")
    
    logger.info(f"✓ Backfilled {len(historical_tweets)} historical tweets")


scraper = TwitterScraper()
