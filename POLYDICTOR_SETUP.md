# Polydictor Setup & Architecture Guide

## 🏗️ Complete Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                         User Layer                           │
│                    (Telegram Interface)                      │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                      Bot Layer                               │
│  • polydictor_bot.py (Commands: /watch, /verify, /mystatus) │
│  • bot.py (Original: /deal, /keywords, /start)              │
└─────────────────────┬───────────────────────────────────────┘
                      │
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
┌──────────────┐ ┌──────────┐ ┌─────────────┐
│ Grok Engine  │ │  Agent   │ │  Payment    │
│  (Brain)     │ │(Executor)│ │  System     │
└──────────────┘ └──────────┘ └─────────────┘
        │             │
        │             ▼
        │    ┌─────────────────┐
        └───▶│ Twitter Stream  │
             └─────────────────┘
```

### Data Flow

1. **User Initiates**: `/watch` + Polymarket URL
2. **Grok Analyzes**: Event → Generates monitoring rules
3. **Agent Sets Up**: Creates Twitter stream with rules
4. **Payment**: User pays USDC → Subscription activated
5. **Processing**: Tweets → Grok analysis → Filtered delivery
6. **Optimization**: Every 6h, Grok refines rules based on metrics

## 🔑 API Keys Setup Guide

### 1. Telegram Bot Token

```bash
# 1. Open Telegram and message @BotFather
# 2. Send: /newbot
# 3. Follow prompts to name your bot
# 4. Copy the token provided

# Add to .env:
BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
```

### 2. Grok API Key (xAI)

```bash
# 1. Visit https://x.ai
# 2. Sign up and create API key
# 3. Select "grok-beta" model access

# Add to .env:
GROK_API_KEY=xai-abc123def456...
```

### 3. Twitter API Bearer Token

```bash
# 1. Go to https://developer.twitter.com/en/portal/dashboard
# 2. Create a new Project & App
# 3. In your app, navigate to "Keys and tokens"
# 4. Generate "Bearer Token"
# 5. IMPORTANT: Enable "Filtered Stream" in app permissions

# Add to .env:
TWITTER_BEARER_TOKEN=AAAAAAAAAAAAAAAAAAAAABc...
```

**Twitter API Tiers:**
- ✅ **Essential** ($100/month): 50 stream rules, 50k tweets/month
- ✅ **Elevated** ($5,000/month): 1000 rules, 2M tweets/month
- ❌ **Free**: No Filtered Stream access

### 4. Payment Wallet (Polygon USDC)

```bash
# 1. Install MetaMask or any Web3 wallet
# 2. Add Polygon network
# 3. Get wallet address (0x...)
# 4. Receive USDC on Polygon

# Add to .env:
PAYMENT_WALLET_ADDRESS=0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb
SUBSCRIPTION_PRICE_USDC=10.0
BLOCKCHAIN_RPC_URL=https://polygon-rpc.com
```

## 🚀 Quick Start

### Option 1: Local Development

```bash
# 1. Clone repo
git clone https://github.com/poly-dictions/polydictions.git
cd polydictions

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp config.py.example config.py
# Edit config.py with your API keys

# Or use .env file:
cat > .env << EOF
BOT_TOKEN=your_telegram_token
GROK_API_KEY=your_grok_key
TWITTER_BEARER_TOKEN=your_twitter_token
PAYMENT_WALLET_ADDRESS=your_polygon_wallet
SUBSCRIPTION_PRICE_USDC=10.0
EOF

# 5. Run bot
python bot.py
```

### Option 2: Docker (Recommended for Production)

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "bot.py"]
```

```bash
# Build and run
docker build -t polydictor .
docker run -d --name polydictor --env-file .env polydictor
```

## 💬 Using the Bot

### Basic Commands

```
/start - Subscribe to new Polymarket events
/help - Show help information
/keywords btc, crypto - Filter events by keywords
/pause - Pause notifications
/resume - Resume notifications
```

### Polydictor Intelligence Commands

```
/watch - Start monitoring an event
/verify <tx_hash> - Verify USDC payment
/mystatus - View active subscriptions
/unwatch <event_slug> - Cancel subscription
```

### Example Session

```
User: /watch
Bot: "Send me a Polymarket event URL..."

User: https://polymarket.com/event/btc-100k-2025
Bot: 🔄 Setting up intelligence monitoring...
     🧠 Asking Grok to analyze event...
     
     ✅ Intelligence Agent Created
     
     📊 Event: Will Bitcoin hit $100k in 2025?
     
     🎯 Monitoring Strategy:
     • Twitter Accounts: 8 verified accounts
     • Keywords: 12 tracked terms
     • Relevance Threshold: 75%
     
     Top Monitored Accounts:
     • @DocumentingBTC
     • @100trillionUSD
     • @APompliano
     
     💰 Payment Instructions
     Amount: 10 USDC
     Network: Polygon
     Address: 0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb

User: /verify 0x9f8a7b6c5d4e3f2a1b0c9d8e7f6a5b4c3d2e1f0...
Bot: 🔄 Verifying payment...
     ✅ Payment Verified! Agent Activated
     
     📡 Now monitoring: Will Bitcoin hit $100k in 2025?
     
     You'll receive:
     • 🔴 High-priority intelligence (immediate)
     • 📊 Hourly digest reports
     • 🧠 Grok-powered analysis

[30 minutes later]

Bot: 🔴 Intelligence Alert
     
     Event: Will Bitcoin hit $100k in 2025?
     From: @100trillionUSD ✅
     Sentiment: Bullish
     Credibility: 94%
     
     Analysis: Stock-to-flow model update shows BTC on track
     for $100k by Q3 2025. Historical patterns align with
     current trajectory.
     
     Priority: HIGH
     Relevance: 96%

[1 hour later]

Bot: 📊 Hourly Intelligence Digest
     
     Summary: Bullish sentiment increased 12% this hour.
     8 high-credibility signals detected.
     
     Sentiment Distribution:
     • Bullish: 72%
     • Neutral: 20%
     • Bearish: 8%
     
     Key Signals:
     1. S2F model update (Cred: 94%)
     2. Institutional buying detected (Cred: 88%)
     3. Technical breakout confirmed (Cred: 85%)
```

## 📊 Intelligence Quality

### What Makes Intelligence "High Priority"?

Grok classifies tweets as high priority when they:
- Come from verified, high-credibility accounts
- Contain breaking news or market-moving information
- Show strong signals (not speculation)
- Have high confidence scores (>85%)

### Credibility Scoring

Factors Grok considers:
- **Account Credibility**: Verified, follower count, expertise
- **Information Quality**: Primary source vs hearsay
- **Track Record**: Historical accuracy (if known)
- **Consensus**: Multiple sources reporting same information

### Sentiment Analysis

- **Bullish**: Information suggests higher probability of event occurring
- **Bearish**: Information suggests lower probability
- **Neutral**: Informational but no clear directional signal

## 🔧 Advanced Configuration

### Custom Grok Prompts

Edit `grok_engine.py` to customize how Grok analyzes events:

```python
# Example: More aggressive filtering
prompt = f"""...
filters:
- relevance_threshold: 0.85  # Higher = stricter
- credibility_threshold: 0.75
...
"""
```

### Adjusting Refinement Schedule

Edit `agent.py`:

```python
# Change refinement interval (default: 6 hours)
await asyncio.sleep(21600)  # 6 hours
# Change to: 10800 for 3 hours, 43200 for 12 hours
```

### Custom Payment Amounts

```python
# .env
SUBSCRIPTION_PRICE_USDC=25.0  # $25 per event
```

## 🐛 Troubleshooting

### Bot Not Starting

```bash
# Check logs
tail -f bot.log

# Common issues:
# 1. Invalid BOT_TOKEN
#    → Verify token from @BotFather
# 2. Missing dependencies
#    → Run: pip install -r requirements.txt
# 3. Port already in use
#    → Kill existing process: pkill -f bot.py
```

### Twitter Stream Not Connecting

```bash
# Test Twitter API access
python << EOF
from twitter_stream import twitter_stream
import asyncio
rules = asyncio.run(twitter_stream.get_active_rules())
print(f"Active rules: {rules}")
EOF

# Common issues:
# 1. Invalid bearer token
# 2. App doesn't have Filtered Stream access
# 3. Rate limit exceeded
```

### Grok Not Responding

```bash
# Test Grok API
python << EOF
from grok_engine import grok_engine
import asyncio
response = asyncio.run(grok_engine._call_grok("test"))
print(response)
EOF

# Common issues:
# 1. Invalid API key
# 2. Rate limit exceeded
# 3. Model not accessible
```

### Payment Verification Failed

```bash
# Check blockchain connection
# Verify transaction on PolygonScan: https://polygonscan.com
# Check wallet address matches config

# For testing, use demo mode:
/verify demo
```

## 📈 Scaling

### Multiple Events

The system automatically handles multiple events:
- Each event gets its own agent
- Agents run independently
- Resources allocated based on subscriber count

### Performance Optimization

```python
# Limit concurrent Grok API calls
GROK_MAX_CONCURRENT = 5

# Batch tweet analysis
ANALYSIS_BATCH_SIZE = 10

# Adjust stream buffer
STREAM_BUFFER_SIZE = 100
```

### Database Migration (Future)

Currently uses JSON files. For production scale:
- Migrate to PostgreSQL for intelligence storage
- Use Redis for caching and pub/sub
- Implement proper database schemas

## 🔐 Security Best Practices

1. **API Keys**: Never commit to git
   ```bash
   # Add to .gitignore
   echo ".env" >> .gitignore
   echo "config.py" >> .gitignore
   ```

2. **Payment Security**: Verify on-chain
   ```python
   # Enable blockchain verification
   USE_BLOCKCHAIN_VERIFICATION = True
   ```

3. **Rate Limiting**: Prevent abuse
   ```python
   MAX_SUBSCRIPTIONS_PER_USER = 5
   COOLDOWN_BETWEEN_WATCHES = 300  # 5 minutes
   ```

4. **Input Validation**: Sanitize user input
   ```python
   # Already implemented in polydictor_bot.py
   event_slug = extract_event_slug(url)  # Validates format
   ```

## 🤝 Contributing

See main README for contribution guidelines.

## 📞 Support

- GitHub Issues: [Report bugs](https://github.com/poly-dictions/polydictions/issues)
- Telegram: [@PolydictorSupport](https://t.me/PolydictorSupport)
- Email: support@polydictor.com

---

**Happy Trading! 🚀**
