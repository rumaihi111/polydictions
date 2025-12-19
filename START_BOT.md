# Quick Start - Mypolydictorbot

## 🚀 Start the Bot in 3 Minutes

### 1. Clone & Install
```bash
git clone https://github.com/rumaihi111/polydictions.git
cd polydictions
pip install -r requirements.txt
```

### 2. Set Up Environment
```bash
# Copy the example
cp .env.example .env

# Edit with your API keys
nano .env  # or use any text editor
```

**Required Keys in `.env`:**
```bash
BOT_TOKEN=your_telegram_bot_token_here
GROK_API_KEY=your_xai_grok_api_key_here
TWITTERAPIO_API_KEY=your_twitterapio_api_key_here
PLATFORM_WALLET_ADDRESS=your_solana_wallet_address_here
WALLET_MASTER_KEY=generate_with_command_below
```

**Generate encryption key:**
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Copy the output to WALLET_MASTER_KEY in .env
```

### 3. Run the Bot
```bash
python bot.py
```

**That's it!** Bot is now running at @Mypolydictorbot

---

## 🛑 Stop the Bot
```bash
# Press Ctrl+C in the terminal
# OR
pkill -f "python.*bot.py"
```

---

## 📋 Where to Get API Keys

| Service | Where to Get | Cost |
|---------|--------------|------|
| **Telegram Bot** | [@BotFather](https://t.me/botfather) | Free |
| **Grok API** | [x.ai](https://x.ai) | Pay-per-use |
| **TwitterAPI.io** | [twitterapi.io](https://twitterapi.io) | $9-29/month |
| **Solana Wallet** | [Phantom](https://phantom.app) or any Solana wallet | Free |

---

## 🔧 Troubleshooting

**"No module named X"**
```bash
pip install -r requirements.txt
```

**"BOT_TOKEN not found"**
- Make sure `.env` file exists in the same directory as `bot.py`
- Check that you didn't name it `.env.txt` (Windows issue)

**Bot doesn't respond**
- Check bot is running: `ps aux | grep bot.py`
- Check logs for errors
- Make sure BOT_TOKEN is correct

---

## 📱 Test the Bot

Send these commands to @Mypolydictorbot:

```
/start - Initialize and see your wallet
/balance - Check USDC balance
/help - See all commands
```

---

## 🔄 Update to Latest Version

```bash
cd polydictions
git pull origin main
pip install -r requirements.txt  # In case dependencies changed
python bot.py
```

---

## 📁 Important Files

- `bot.py` - Main bot script (START THIS)
- `.env` - Your API keys (NEVER commit to git!)
- `requirements.txt` - Python dependencies
- User data saved in `.json` files (auto-created)

---

## 🆘 Common Issues

**Issue:** Bot starts but doesn't respond to commands
**Fix:** Make sure you're messaging the correct bot (@Mypolydictorbot)

**Issue:** "Wallet encryption warning"
**Fix:** Add `WALLET_MASTER_KEY` to `.env` (see step 2 above)

**Issue:** Bot crashes on startup
**Fix:** Check you have all required keys in `.env`

---

## 💡 Pro Tips

**Run in background:**
```bash
nohup python bot.py > bot.log 2>&1 &
```

**Check if running:**
```bash
ps aux | grep bot.py
```

**View logs:**
```bash
tail -f bot.log
```

**Run on server restart (systemd):**
Create `/etc/systemd/system/polydictor.service`:
```ini
[Unit]
Description=Polydictor Telegram Bot
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/path/to/polydictions
ExecStart=/usr/bin/python3 bot.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl enable polydictor
sudo systemctl start polydictor
```

---

## ✅ That's All You Need!

Just run `python bot.py` and the bot is live. No complex setup, no multiple files to run.
