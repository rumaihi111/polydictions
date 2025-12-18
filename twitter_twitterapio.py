"""
TwitterAPI.io Integration
Provides Advanced Search, Filter Rules, and User Monitoring via twitterapi.io
"""
import os
import logging
import requests
import json
import time
import threading
import asyncio
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta

try:
    import websocket
except ImportError:
    websocket = None

logger = logging.getLogger(__name__)

class TwitterApiIO:
    """
    TwitterAPI.io client for tweet search and streaming.
    Cost-effective alternative to Twitter API v2 Elevated access.
    """
    
    BASE_URL = "https://api.twitterapi.io"
    WEBSOCKET_URL = "wss://ws.twitterapi.io/twitter/tweet/websocket"
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize TwitterAPI.io client.
        
        Args:
            api_key: API key from twitterapi.io (or set TWITTERAPIO_API_KEY env var)
        """
        self.api_key = api_key or os.getenv('TWITTERAPIO_API_KEY')
        if not self.api_key:
            raise ValueError("TWITTERAPIO_API_KEY not found in environment")
        
        # WebSocket state
        self.ws = None
        self.ws_thread = None
        self.tweet_callback = None
        self.is_running = False
        
        self.headers = {
            'X-API-Key': self.api_key
        }
    
    def advanced_search(
        self,
        query: str,
        query_type: str = 'Latest',
        cursor: str = '',
        max_results: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Search for tweets using Twitter's advanced search syntax.
        
        Args:
            query: Search query using Twitter syntax
                   Examples:
                   - "bitcoin" OR "BTC" (keywords)
                   - from:elonmusk (specific user)
                   - since:2025-12-18_00:00:00_UTC (date range)
                   - "AI" -ads (exclude terms)
                   Full syntax: https://github.com/igorbrigadir/twitter-advanced-search
            
            query_type: 'Latest' for chronological or 'Top' for most relevant
            cursor: Pagination cursor (empty string for first page)
            max_results: Maximum tweets to fetch (fetches all if None, up to 20/page)
        
        Returns:
            {
                'tweets': [...],  # List of tweet objects
                'has_next_page': bool,
                'next_cursor': str,
                'total_fetched': int  # Total tweets fetched (if max_results used)
            }
        """
        all_tweets = []
        current_cursor = cursor
        
        while True:
            params = {
                'query': query,
                'queryType': query_type,
                'cursor': current_cursor
            }
            
            try:
                response = requests.get(
                    f"{self.BASE_URL}/twitter/tweet/advanced_search",
                    headers=self.headers,
                    params=params,
                    timeout=30
                )
                response.raise_for_status()
                data = response.json()
                
                tweets = data.get('tweets', [])
                all_tweets.extend(tweets)
                
                logger.info(f"Fetched {len(tweets)} tweets for query: {query[:50]}...")
                
                # Check if we should continue pagination
                has_next = data.get('has_next_page', False)
                
                if max_results and len(all_tweets) >= max_results:
                    # Trim to max_results
                    all_tweets = all_tweets[:max_results]
                    break
                
                if not has_next:
                    break
                
                if max_results is None:
                    # If no max_results, only fetch first page
                    break
                
                current_cursor = data.get('next_cursor', '')
                if not current_cursor:
                    break
                    
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 400:
                    error_data = e.response.json()
                    logger.error(f"Invalid search query: {error_data.get('message', 'Unknown error')}")
                    logger.error(f"Query was: {query}")
                raise Exception(f"Advanced search failed: {str(e)}")
            except Exception as e:
                logger.error(f"Advanced search error: {str(e)}")
                raise
        
        return {
            'tweets': all_tweets,
            'has_next_page': data.get('has_next_page', False) if all_tweets else False,
            'next_cursor': data.get('next_cursor', '') if all_tweets else '',
            'total_fetched': len(all_tweets)
        }
    
    def backfill_recent_tweets(
        self,
        keywords: List[str],
        accounts: List[str],
        hours_back: int = 48,
        max_results: int = 100
    ) -> Dict[str, Any]:
        """
        Backfill recent tweets for initial context.
        Combines keywords and accounts into optimized search queries.
        
        Args:
            keywords: List of keywords/phrases to search
            accounts: List of Twitter usernames (without @)
            hours_back: How many hours back to search
            max_results: Maximum tweets to fetch
        
        Returns:
            {
                'tweets': [...],
                'total_fetched': int,
                'queries_used': [str]
            }
        """
        # Calculate since timestamp
        since_time = datetime.utcnow() - timedelta(hours=hours_back)
        since_str = since_time.strftime('%Y-%m-%d_%H:%M:%S_UTC')
        
        # Build query combining keywords and accounts
        query_parts = []
        
        # Add keywords
        if keywords:
            keyword_query = ' OR '.join(f'"{kw}"' for kw in keywords[:10])  # Limit to 10 keywords
            query_parts.append(f"({keyword_query})")
        
        # Add accounts
        if accounts:
            account_query = ' OR '.join(f'from:{acc}' for acc in accounts[:5])  # Limit to 5 accounts
            query_parts.append(f"({account_query})")
        
        # Combine with AND/OR logic
        if len(query_parts) > 1:
            query = ' OR '.join(query_parts)
        elif query_parts:
            query = query_parts[0]
        else:
            raise ValueError("Must provide at least keywords or accounts")
        
        # Add time filter
        query += f" since:{since_str}"
        
        logger.info(f"Backfilling tweets with query: {query}")
        
        result = self.advanced_search(
            query=query,
            query_type='Latest',
            max_results=max_results
        )
        
        return {
            'tweets': result['tweets'],
            'total_fetched': result['total_fetched'],
            'queries_used': [query],
            'time_range': f"Last {hours_back} hours"
        }
    
    def extract_intelligence(self, tweet: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract key intelligence fields from a tweet for Grok analysis.
        
        Args:
            tweet: Raw tweet object from API
        
        Returns:
            Cleaned tweet with intelligence signals
        """
        author = tweet.get('author', {})
        entities = tweet.get('entities', {})
        
        return {
            # Core content
            'id': tweet.get('id'),
            'url': tweet.get('url'),
            'text': tweet.get('text'),
            'created_at': tweet.get('createdAt'),
            
            # Engagement metrics (credibility signals)
            'engagement': {
                'retweets': tweet.get('retweetCount', 0),
                'replies': tweet.get('replyCount', 0),
                'likes': tweet.get('likeCount', 0),
                'quotes': tweet.get('quoteCount', 0),
                'views': tweet.get('viewCount', 0),
                'bookmarks': tweet.get('bookmarkCount', 0)
            },
            
            # Author credibility
            'author': {
                'username': author.get('userName'),
                'name': author.get('name'),
                'verified': author.get('isBlueVerified', False),
                'followers': author.get('followers', 0),
                'is_bot': author.get('isAutomated', False),
                'tweet_count': author.get('statusesCount', 0)
            },
            
            # Context
            'is_reply': tweet.get('isReply', False),
            'conversation_id': tweet.get('conversationId'),
            'has_quote': tweet.get('quoted_tweet') is not None,
            'is_retweet': tweet.get('retweeted_tweet') is not None,
            
            # Entities (for network analysis)
            'hashtags': [h.get('text') for h in entities.get('hashtags', [])],
            'mentions': [m.get('screen_name') for m in entities.get('user_mentions', [])],
            'urls': [u.get('expanded_url') for u in entities.get('urls', [])]
        }
    
    def format_for_grok(self, tweets: List[Dict[str, Any]]) -> str:
        """
        Format tweets for Grok analysis.
        
        Args:
            tweets: List of raw tweet objects
        
        Returns:
            Formatted string for Grok prompt
        """
        if not tweets:
            return "No recent tweets found."
        
        formatted_tweets = []
        for tweet in tweets[:50]:  # Limit to 50 tweets for context size
            intel = self.extract_intelligence(tweet)
            
            # Skip bot tweets
            if intel['author']['is_bot']:
                continue
            
            engagement_score = (
                intel['engagement']['likes'] + 
                intel['engagement']['retweets'] * 2 + 
                intel['engagement']['quotes'] * 3
            )
            
            formatted_tweets.append(
                f"[@{intel['author']['username']}] "
                f"(👤{intel['author']['followers']:,} followers, "
                f"{'✓' if intel['author']['verified'] else '○'}) "
                f"[💫{engagement_score:,}]: "
                f"{intel['text'][:200]}"
            )
        
        return "\n\n".join(formatted_tweets)
    
    def add_user_to_monitor(self, username: str) -> Dict[str, Any]:
        """
        Add a Twitter user to monitor for tweet streaming.
        
        This sets up monitoring for ALL tweet types from the user:
        - Original tweets
        - Retweets
        - Quote tweets
        - Replies
        
        Tweets will be delivered via WebSocket connection.
        
        Args:
            username: Twitter username (without @)
        
        Returns:
            {
                'status': 'success',
                'msg': str
            }
        
        Raises:
            Exception: If user doesn't exist or API error
        """
        # Remove @ if provided
        username = username.lstrip('@')
        
        payload = {
            'x_user_name': username
        }
        
        try:
            response = requests.post(
                f"{self.BASE_URL}/oapi/x_user_stream/add_user_to_monitor_tweet",
                headers={
                    'X-API-Key': self.api_key,
                    'Content-Type': 'application/json'
                },
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            logger.info(f"Added user monitoring: @{username}")
            return data
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 400:
                error_data = e.response.json()
                logger.error(f"Failed to add user: {error_data.get('message', 'Unknown error')}")
                raise Exception(f"Invalid username or user doesn't exist: @{username}")
            raise Exception(f"User monitoring failed: {str(e)}")
        except Exception as e:
            logger.error(f"Error adding user to monitor: {str(e)}")
            raise
    
    def add_multiple_users_to_monitor(self, usernames: List[str]) -> Dict[str, Any]:
        """
        Add multiple Twitter users to monitor.
        
        Args:
            usernames: List of Twitter usernames (with or without @)
        
        Returns:
            {
                'successful': [usernames],
                'failed': [{'username': str, 'error': str}],
                'total_added': int
            }
        """
        successful = []
        failed = []
        
        for username in usernames:
            try:
                result = self.add_user_to_monitor(username)
                successful.append(username.lstrip('@'))
            except Exception as e:
                failed.append({
                    'username': username,
                    'error': str(e)
                })
        
        logger.info(f"User monitoring: {len(successful)} added, {len(failed)} failed")
        
        return {
            'successful': successful,
            'failed': failed,
            'total_added': len(successful)
        }
    
    def remove_user_from_monitor(self, user_id: str) -> Dict[str, Any]:
        """
        Remove a Twitter user from monitoring.
        
        Args:
            user_id: Twitter user ID or username to stop monitoring
        
        Returns:
            {
                'status': 'success',
                'msg': str
            }
        
        Raises:
            Exception: If user not found or API error
        """
        payload = {
            'id_for_user': user_id
        }
        
        try:
            response = requests.post(
                f"{self.BASE_URL}/oapi/x_user_stream/remove_user_to_monitor_tweet",
                headers={
                    'X-API-Key': self.api_key,
                    'Content-Type': 'application/json'
                },
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            logger.info(f"Removed user monitoring: {user_id}")
            return data
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 400:
                error_data = e.response.json()
                logger.error(f"Failed to remove user: {error_data.get('message', 'Unknown error')}")
                raise Exception(f"User not found in monitoring: {user_id}")
            raise Exception(f"User removal failed: {str(e)}")
        except Exception as e:
            logger.error(f"Error removing user from monitor: {str(e)}")
            raise
    
    def remove_multiple_users_from_monitor(self, user_ids: List[str]) -> Dict[str, Any]:
        """
        Remove multiple Twitter users from monitoring.
        
        Args:
            user_ids: List of Twitter user IDs or usernames to stop monitoring
        
        Returns:
            {
                'successful': [user_ids],
                'failed': [{'user_id': str, 'error': str}],
                'total_removed': int
            }
        """
        successful = []
        failed = []
        
        for user_id in user_ids:
            try:
                result = self.remove_user_from_monitor(user_id)
                successful.append(user_id)
            except Exception as e:
                failed.append({
                    'user_id': user_id,
                    'error': str(e)
                })
        
        logger.info(f"User monitoring removal: {len(successful)} removed, {len(failed)} failed")
        
        return {
            'successful': successful,
            'failed': failed,
            'total_removed': len(successful)
        }
    
    # ===== WebSocket Streaming =====
    
    def _on_message(self, ws, message):
        """WebSocket message handler"""
        try:
            data = json.loads(message)
            event_type = data.get("event_type")
            
            if event_type == "connected":
                logger.info("WebSocket connected successfully")
                return
                
            if event_type == "ping":
                timestamp = data.get("timestamp", 0)
                current_time_ms = time.time() * 1000
                latency_ms = current_time_ms - timestamp
                logger.debug(f"WebSocket ping (latency: {latency_ms:.0f}ms)")
                return
            
            if event_type == "tweet":
                rule_id = data.get("rule_id")
                rule_tag = data.get("rule_tag")
                tweets = data.get("tweets", [])
                timestamp = data.get("timestamp", 0)
                
                logger.info(f"Received {len(tweets)} tweets for rule_tag: {rule_tag}")
                
                # Call the user-provided callback if set
                if self.tweet_callback:
                    try:
                        # Call callback with extracted data
                        self.tweet_callback({
                            'rule_id': rule_id,
                            'rule_tag': rule_tag,
                            'tweets': tweets,
                            'timestamp': timestamp,
                            'event_type': event_type
                        })
                    except Exception as e:
                        logger.error(f"Error in tweet callback: {e}")
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {e}")
        except Exception as e:
            logger.error(f"Error processing WebSocket message: {e}")
    
    def _on_error(self, ws, error):
        """WebSocket error handler"""
        logger.error(f"WebSocket error: {error}")
    
    def _on_close(self, ws, close_status_code, close_msg):
        """WebSocket close handler"""
        logger.info(f"WebSocket closed (code: {close_status_code}, msg: {close_msg})")
        self.is_running = False
        
        if close_status_code == 1006:
            logger.warning("Abnormal WebSocket closure - possible network issue")
    
    def _on_open(self, ws):
        """WebSocket open handler"""
        logger.info("WebSocket connection opened")
        self.is_running = True
    
    def start_websocket_stream(self, tweet_callback: Callable[[Dict], None]):
        """
        Start WebSocket connection to receive tweets in real-time.
        
        Args:
            tweet_callback: Function to call when tweets are received.
                           Receives dict with: rule_id, rule_tag, tweets, timestamp
        
        Example:
            def handle_tweets(data):
                for tweet in data['tweets']:
                    print(f"New tweet: {tweet['text']}")
            
            client.start_websocket_stream(handle_tweets)
        """
        if websocket is None:
            raise ImportError("websocket-client library not installed. Run: pip install websocket-client")
        
        if self.is_running:
            logger.warning("WebSocket stream already running")
            return
        
        self.tweet_callback = tweet_callback
        
        headers = {"x-api-key": self.api_key}
        
        self.ws = websocket.WebSocketApp(
            self.WEBSOCKET_URL,
            header=headers,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
            on_open=self._on_open
        )
        
        # Run in separate thread
        self.ws_thread = threading.Thread(
            target=lambda: self.ws.run_forever(
                ping_interval=40,
                ping_timeout=30,
                reconnect=90
            ),
            daemon=True
        )
        self.ws_thread.start()
        
        logger.info("WebSocket stream started in background thread")
    
    def stop_websocket_stream(self):
        """Stop the WebSocket connection"""
        if self.ws:
            self.ws.close()
            self.is_running = False
            logger.info("WebSocket stream stopped")


if __name__ == "__main__":
    # Test the implementation
    import sys
    from dotenv import load_dotenv
    
    load_dotenv()
    logging.basicConfig(level=logging.INFO)
    
    # Simple test callback for WebSocket
    def test_callback(data):
        print(f"\n🔔 Received {len(data['tweets'])} tweets for rule: {data['rule_tag']}")
        for tweet in data['tweets'][:2]:
            print(f"  - @{tweet.get('author', {}).get('userName')}: {tweet.get('text', '')[:80]}")
    
    try:
        client = TwitterApiIO()
        
        print("\n" + "="*60)
        print("TEST 1: Advanced Search")
        print("="*60)
        
        # Test simple search (first page only to avoid rate limits)
        result = client.advanced_search(
            query='bitcoin OR BTC',
            query_type='Latest',
            max_results=None  # First page only
        )
        
        print(f"\n✅ Fetched {result['total_fetched']} tweets")
        print(f"\nFormatted for Grok (first 3):")
        print(client.format_for_grok(result['tweets'][:3]))
        
        print("\n" + "="*60)
        print("TEST 2: User Monitoring")
        print("="*60)
        
        # Test adding users to monitor
        test_users = ['elonmusk']
        monitor_result = client.add_multiple_users_to_monitor(test_users)
        
        print(f"\n✅ Added {monitor_result['total_added']} users to monitoring")
        print(f"Users: {', '.join('@' + u for u in monitor_result['successful'])}")
        
        print("\n" + "="*60)
        print("TEST 3: WebSocket Streaming")
        print("="*60)
        
        print("\n⚠️  WebSocket streaming is available!")
        print("    Run test_websocket.py for full WebSocket test")
        print("    client.start_websocket_stream(callback_function)")
        
    except Exception as e:
        print(f"Error: {e}")
