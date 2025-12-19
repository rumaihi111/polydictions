# Polydictor: Agentic Twitter Intelligence Platform

**Real-time Twitter intelligence for Polymarket prediction markets, powered by AI**

Polydictor is an AI-powered intelligence platform that monitors Twitter for Polymarket events. Users paste a Polymarket URL, and an AI agent automatically configures monitoring, analyzes tweets, and delivers actionable insights via Telegram.

## 🚀 Quick Start

**Want to run the bot right now?** See **[START_BOT.md](START_BOT.md)** - 3 minute setup!

```bash
git clone https://github.com/rumaihi111/polydictions.git
cd polydictions
cp .env.example .env
# Edit .env with your API keys
pip install -r requirements.txt
python bot.py
```

## 🎯 Overview

Polydictor transforms prediction market research by:
- **Automated Monitoring**: AI configures Twitter monitoring based on event context
- **Real-time Analysis**: Every relevant tweet analyzed by Grok for credibility & sentiment
- **Intelligent Delivery**: High-priority signals sent immediately, others synthesized hourly
- **Self-Optimization**: Rules refined every 6 hours based on performance metrics

## 🏗️ Architecture

### The Grok Rule Engine Model

**Grok = Brain** (Makes all decisions)
- Generates monitoring rules (accounts, keywords, filters)
- Analyzes tweets when requested by agent
- Refines rules every 6 hours based on performance
- Makes all strategic decisions

**Agent = Executor** (Follows instructions mechanically)
- Applies Grok's rules
- Fetches tweets via Twitter API
- Routes intelligence to users
- Reports performance metrics back to Grok
- NO independent decision-making

## 📊 System Flow

```
1. User Submits Event (Polymarket URL via Telegram)
   ↓
2. Grok Generates Initial Ruleset
   • Searches Twitter for relevant accounts
   • Generates event-specific keywords
   • Defines filtering rules (relevance, credibility)
   • Sets priority classification rules
   ↓
3. Agent Setup
   • Validates accounts via Twitter API
   • Creates Twitter Filtered Stream rule
   • Spawns agent instance
   ↓
4. User Subscribes (USDC payment)
   ↓
5. Continuous Processing
   • Twitter stream delivers tagged tweets
   • Agent applies Grok's filtering rules
   • Passes filters → Agent asks Grok for analysis
   • Grok returns: relevance, sentiment, credibility, insights
   • Agent stores and delivers based on priority
   ↓
6. Hourly Synthesis
   • Agent collects past hour's intelligence
   • Grok synthesizes into digest
   • Digest delivered to all subscribers
   ↓
7. Rule Refinement (Every 6 Hours)
   • Agent reports performance metrics
   • Grok analyzes and generates updated ruleset
   • Agent applies new rules
   • System self-optimizes
```

## 🚀 Features

### For Users
- **Simple Setup**: Just paste a Polymarket URL
- **Real-time Intelligence**: High-priority signals delivered immediately
- **Hourly Digests**: Synthesized summaries of all activity
- **Credibility Scoring**: Every tweet rated for trustworthiness
- **Sentiment Analysis**: Understand market sentiment shifts
- **Affordable**: ~$10 USDC per event (low Polygon fees)

### For the System
- **Adaptive Learning**: Rules improve based on performance
- **Scalable**: Each event gets its own agent
- **Efficient**: Twitter Filtered Streams (no polling)
- **Persistent**: All intelligence stored for analysis

## 📦 Installation

### Prerequisites


- Python 3.8 or higher
- A Telegram Bot Token from [@BotFather](https://t.me/BotFather)

### Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/polydictions.git
cd polydictions
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a configuration file:
```bash
# Create config.py with your bot token
echo BOT_TOKEN = "your_bot_token_here" > config.py
```

Alternatively, create a `.env` file:
```bash
BOT_TOKEN=your_bot_token_here
```

4. Run the bot:
```bash
python bot.py
```

## Configuration

The bot uses the following files for data persistence:

- `users.json` - Stores subscribed user IDs
- `seen_events.json` - Tracks processed events
- `keywords.json` - Stores user keyword filters
- `paused_users.json` - Tracks users who paused notifications

These files are automatically created and managed by the bot.

## Usage Examples

### Analyze an Event
```
/deal https://polymarket.com/event/presidential-election-winner-2024
```

### Set Keyword Filters
```
/keywords btc, eth, crypto
/keywords "artificial intelligence", tech
/keywords clear
```

The bot supports:
- Simple keywords: `btc`, `election`, `sports`
- Phrases with quotes: `"united states"`, `"world cup"`
- Multiple keywords (OR logic): `btc, eth, sports`

### Pause and Resume
```
/pause    # Stop receiving notifications
/resume   # Start receiving notifications again
```

## API Integration

The bot integrates with:
- **Polymarket Gamma API**: For event data and market information
- **Polymarket Grok API**: For AI-generated market context

## Project Structure

```
polydictions/
├── bot.py              # Main bot application
├── config.py           # Configuration (token)
├── requirements.txt    # Python dependencies
├── .gitignore         # Git ignore rules
└── README.md          # Documentation
```

## Contributing

Contributions are welcome. Please feel free to submit a Pull Request.

## License

This project is open source and available under the MIT License.

## Disclaimer

This bot is for informational purposes only. Always do your own research before making any predictions or financial decisions.
