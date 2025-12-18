# Polydictor Quick Reference

## 🚀 Getting Started

```bash
# 1. Install
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Edit .env with your API keys

# 3. Run
python run.py
```

## 💬 Bot Commands

### Original Polydictions Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/start` | Subscribe to new events | `/start` |
| `/deal` | Analyze specific event | `/deal https://polymarket.com/event/...` |
| `/keywords` | Set keyword filters | `/keywords btc, crypto` |
| `/pause` | Pause notifications | `/pause` |
| `/resume` | Resume notifications | `/resume` |
| `/help` | Show help | `/help` |

### Polydictor Intelligence Commands (NEW)

| Command | Description | Example |
|---------|-------------|---------|
| `/watch` | Start event monitoring | `/watch` → paste URL |
| `/verify` | Verify USDC payment | `/verify 0x123abc...` |
| `/verify demo` | Demo mode (skip payment) | `/verify demo` |
| `/mystatus` | View subscriptions | `/mystatus` |
| `/unwatch` | Cancel subscription | `/unwatch btc-100k-2025` |

## 🔄 User Flow

```
┌─────────────────────────────────────┐
│  1. /watch                          │
│     Bot: "Send Polymarket URL..."   │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  2. Paste URL                       │
│     https://polymarket.com/event/...|
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  3. Bot Creates Agent               │
│     • Grok analyzes event           │
│     • Generates monitoring rules    │
│     • Shows payment info            │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  4. User Pays (or /verify demo)     │
│     Send 10 USDC to Polygon wallet  │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  5. /verify <tx_hash>               │
│     Bot verifies & activates agent  │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  6. Receive Intelligence            │
│     • Real-time alerts (high pri)   │
│     • Hourly digests (all activity) │
│     • Auto-refined every 6 hours    │
└─────────────────────────────────────┘
```

## 🎯 Intelligence Types

### High Priority (Immediate Delivery)
```
🔴 Intelligence Alert

Event: Will Bitcoin hit $100k?
From: @credibleSource ✅
Sentiment: Bullish
Credibility: 94%

Analysis: [Grok's insights]
Priority: HIGH
Relevance: 96%
```

### Hourly Digest
```
📊 Hourly Intelligence Digest

Summary: [Overview of hour's activity]

Sentiment Distribution:
• Bullish: 72%
• Neutral: 20%
• Bearish: 8%

Key Signals:
1. [Top signal 1]
2. [Top signal 2]
3. [Top signal 3]

Confidence: High
```

## 📊 What Grok Monitors

### For Each Event, Grok Creates:

1. **Account List** (5-10 Twitter accounts)
   - Verified experts
   - News sources
   - Key influencers
   - Official accounts

2. **Keyword List** (10-15 terms)
   - Event-specific terms
   - Abbreviations
   - Hashtags
   - Related concepts

3. **Filter Rules**
   - Relevance threshold (0-100%)
   - Credibility threshold (0-100%)
   - Exclude patterns (spam, bots)

4. **Priority Rules**
   - High: Breaking news, verified info
   - Medium: Analysis, discussion
   - Low: Speculation, tangential

## 🔧 Configuration

### .env Variables

```bash
# Required
BOT_TOKEN=              # Telegram bot token
GROK_API_KEY=           # xAI Grok API key
TWITTER_BEARER_TOKEN=   # Twitter API v2 token

# Payment (Required for real payments)
PAYMENT_WALLET_ADDRESS= # Your Polygon wallet
SUBSCRIPTION_PRICE_USDC=10.0

# Optional
BLOCKCHAIN_RPC_URL=     # Polygon RPC endpoint
```

### Getting API Keys

**Telegram:**
1. Message @BotFather
2. `/newbot`
3. Copy token

**Grok (xAI):**
1. Visit https://x.ai
2. Sign up
3. Create API key

**Twitter:**
1. Go to https://developer.twitter.com
2. Create project + app
3. Get Bearer Token
4. Enable "Filtered Stream"
5. Need: Essential tier ($100/mo) or higher

## 🐛 Troubleshooting

### Bot won't start
```bash
# Check logs
tail -f polydictor.log

# Verify config
cat .env
```

### Agent not processing tweets
```bash
# Check Twitter stream status
python -c "
from twitter_stream import twitter_stream
import asyncio
print(asyncio.run(twitter_stream.get_active_rules()))
"
```

### Grok not responding
```bash
# Test Grok API
python -c "
from grok_engine import grok_engine
import asyncio
print(asyncio.run(grok_engine._call_grok('test')))
"
```

### Payment issues
- Check wallet address is correct
- Verify network is Polygon
- Confirm USDC (not MATIC)
- Check transaction on PolygonScan
- For testing: use `/verify demo`

## 📈 Performance Metrics

View your subscription status:
```
/mystatus

Response shows:
• Event name
• Agent status
• Intelligence count
• High priority count
• Average relevance
• Start date
```

## 🔐 Security

- Never share API keys
- Use `.env` (not committed to git)
- Verify payment wallet address
- Check transaction hashes
- Keep bot token secret

## 💡 Tips

1. **Testing**: Use `/verify demo` to skip payment
2. **Multiple Events**: Create separate subscriptions
3. **High Volume Events**: Expect more frequent updates
4. **Refinement**: Let agent run 6+ hours for optimization
5. **Metrics**: Check `/mystatus` regularly

## 📞 Support

- Issues: GitHub Issues
- Chat: @PolydictorSupport
- Email: support@polydictor.com

## 🎓 Example Session

```
You: /watch
Bot: Send me a Polymarket URL...

You: https://polymarket.com/event/btc-100k-2025
Bot: 🔄 Setting up...
     ✅ Agent created
     💰 Send 10 USDC to: 0x...

You: /verify demo
Bot: ✅ Agent Activated!

[5 min later]
Bot: 🔴 Intelligence Alert
     High-priority signal detected!
     [Details...]

[1 hour later]
Bot: 📊 Hourly Digest
     [Summary of all activity...]
```

## 🚀 Pro Tips

1. **Watch multiple events** - Each gets independent monitoring
2. **Check digests daily** - Synthesized intelligence is valuable
3. **Trust high-priority alerts** - Pre-filtered by Grok
4. **Monitor metrics** - See what's working via `/mystatus`
5. **Let it learn** - 6-hour refinements improve over time

---

**Happy Trading! 🎯**
