"""
Test WebSocket streaming from twitterapi.io
"""
import time
from dotenv import load_dotenv
from twitter_twitterapio import TwitterApiIO
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def handle_tweets(data):
    """Callback for when tweets are received"""
    print("\n" + "="*60)
    print(f"📨 RECEIVED TWEETS")
    print("="*60)
    print(f"Rule Tag: {data['rule_tag']}")
    print(f"Rule ID: {data['rule_id']}")
    print(f"Tweet Count: {len(data['tweets'])}")
    print(f"Timestamp: {data['timestamp']}")
    
    for i, tweet in enumerate(data['tweets'][:3], 1):  # Show first 3 tweets
        print(f"\n--- Tweet {i} ---")
        print(f"Author: @{tweet.get('author', {}).get('userName', 'unknown')}")
        print(f"Text: {tweet.get('text', '')[:200]}")
        print(f"Likes: {tweet.get('likeCount', 0)} | Retweets: {tweet.get('retweetCount', 0)}")
    
    if len(data['tweets']) > 3:
        print(f"\n... and {len(data['tweets']) - 3} more tweets")
    
    print("="*60)

def main():
    load_dotenv()
    
    print("\n🚀 Starting TwitterAPI.io WebSocket Test")
    print("="*60)
    
    client = TwitterApiIO()
    
    # First, add a user to monitor
    print("\n1️⃣  Adding @elonmusk to monitoring...")
    try:
        result = client.add_user_to_monitor('elonmusk')
        print(f"✅ User added: {result}")
    except Exception as e:
        print(f"⚠️  User may already be added: {e}")
    
    # Start WebSocket stream
    print("\n2️⃣  Starting WebSocket stream...")
    client.start_websocket_stream(handle_tweets)
    
    print("\n✅ WebSocket connected! Waiting for tweets...")
    print("⏳ Note: Tweets are batched and delivered every ~100 seconds")
    print("🛑 Press Ctrl+C to stop\n")
    
    try:
        # Keep running
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n🛑 Stopping WebSocket...")
        client.stop_websocket_stream()
        print("✅ Stopped")

if __name__ == "__main__":
    main()
