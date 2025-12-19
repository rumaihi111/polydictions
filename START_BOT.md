# Quick Start - Mypolydictorbot (Local Machine)

## 🚀 Run the Bot on Your Computer

### Prerequisites
- Python 3.10+ ([Download Python](https://www.python.org/downloads/))
- Git ([Download Git](https://git-scm.com/downloads))
- A terminal/command prompt

### 1. Clone the Repository
**Open Terminal (Mac/Linux) or Command Prompt (Windows):**

```bash
git clone https://github.com/rumaihi111/polydictions.git
cd polydictions
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

**If `pip` doesn't work, try:**
- Windows: `py -m pip install -r requirements.txt`
- Mac/Linux: `pip3 install -r requirements.txt`

### 3. Set Up Your API Keys

**Copy the example file:**
```bash
# Mac/Linux
cp .env.example .env

# Windows
copy .env.example .env
```

**Edit the `.env` file:**
- **Mac/Linux:** `nano .env` or use any text editor
- **Windows:** `notepad .env` or use Notepad++

**Add your keys:**
```bash
BOT_TOKEN=8166624440:AAGdlZ4QJUM_RG6tmAnGiK1DDogqNySPwVQ
GROK_API_KEY=your_xai_key_here
TWITTERAPIO_API_KEY=your_twitter_api_key_here
PLATFORM_WALLET_ADDRESS=your_solana_address_here
WALLET_MASTER_KEY=generate_this_next
```

**Generate encryption key:**
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
Copy the output and paste it as `WALLET_MASTER_KEY` in your `.env` file.

### 4. Run the Bot
```bash
python bot.py
```

**If `python` doesn't work:**
- Windows: `py bot.py`
- Mac/Linux: `python3 bot.py`

**You should see:**
```
INFO - Bot menu commands set up successfully
INFO - Bot started with API server on port 8765
INFO - Run polling for bot @Mypolydictorbot
```

✅ **Bot is now running!** Send `/start` to @Mypolydictorbot on Telegram.

---

## 🛑 Stop the Bot

**Just press `Ctrl+C` in the terminal**

---

## 🔄 Run the Bot Again Later

1. Open terminal
2. Navigate to folder: `cd polydictions` (or `cd path/to/polydictions`)
3. Run: `python bot.py`

**That's it!** No need to reinstall or reconfigure.

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

## � Folder Location Tips

**Where did I download it?**
- Mac: Usually in `/Users/yourname/polydictions`
- Windows: Usually in `C:\Users\YourName\polydictions`
- Check Downloads folder if you're not sure

**To find it:**
```bash
# Mac/Linux
pwd  # Shows current directory

# Windows
cd  # Shows current directory
```

**Navigate to it next time:**
```bash
cd polydictions
```

Or use the full path:
```bash
# Mac example
cd /Users/yourname/polydictions

# Windows example
cd C:\Users\YourName\polydictions
```

---

## 💻 Keep the Terminal Open

**Important:** The bot runs AS LONG AS the terminal is open!

- ✅ Terminal open = Bot running
- ❌ Close terminal = Bot stops

**Want it to run 24/7?** See "Run in Background" below.

---

## 🌙 Run in Background (Mac/Linux)

**Keep bot running even after closing terminal:**
```bash
nohup python bot.py > bot.log 2>&1 &
```

**Check if it's running:**
```bash
ps aux | grep bot.py
```

**Stop it:**
```bash
pkill -f "python.*bot.py"
```

**View logs:**
```bash
tail -f bot.log
```

---

## 🪟 Run in Background (Windows)

**Option 1: Use pythonw (silent background)**
```cmd
pythonw bot.py
```

**Option 2: Use Task Scheduler**
1. Open Task Scheduler
2. Create Basic Task
3. Action: Start a program
4. Program: `python`
5. Arguments: `bot.py`
6. Start in: `C:\path\to\polydictions`

**Stop it:**
- Open Task Manager (`Ctrl+Shift+Esc`)
- Find "python.exe" running bot.py
- End task

---

## �🔧 Troubleshooting

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
