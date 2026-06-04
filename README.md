# 🎬 Telegram Video Downloader Bot

Downloads videos from TikTok, YouTube Shorts, Instagram Reels, and Facebook.  
Built with **aiogram 3.x** and **yt-dlp**.

---

## 📁 Project structure

```
├── bot.py           # Entry point
├── config.py        # All settings & constants
├── handlers.py      # Telegram message handlers
├── downloader.py    # yt-dlp download logic
├── user_logger.py   # Logs every successful download
├── requirements.txt
├── nixpacks.toml    # Tells Railway to install ffmpeg
├── railway.toml     # Railway deployment config
├── .env.example     # Copy → .env for local dev
└── .gitignore
```

---

## 🔑 Admin mode (ID: your Telegram ID)

When **you** send a link the bot uses:
- `bestvideo+bestaudio` merged via ffmpeg → best possible quality
- Up to **500 MB** download cap (vs 50 MB for regular users)

> ⚠️ **Telegram's standard Bot API caps file uploads at 50 MB.**  
> Files larger than 50 MB can only be sent if you run a  
> [local Bot API server](https://core.telegram.org/bots/api#using-a-local-bot-api-server).  
> For most videos (shorts, reels, TikToks) best quality is well under 50 MB.

---

## 🖥 Local development

```bash
# 1. Clone and enter the project
git clone https://github.com/your-username/your-repo.git
cd your-repo

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create .env file
cp .env.example .env
# Edit .env and paste your BOT_TOKEN

# 5. Run
python bot.py
```

---

## 🚀 Deploy to Railway

### Step 1 — Push to GitHub
```bash
git init
git add .
git commit -m "initial commit"
git branch -M main
git remote add origin https://github.com/your-username/your-repo.git
git push -u origin main
```

### Step 2 — Create Railway project
1. Go to [railway.app](https://railway.app) → **New Project**
2. Choose **Deploy from GitHub repo**
3. Select your repository

### Step 3 — Set environment variable
In Railway dashboard → your service → **Variables** tab:
```
BOT_TOKEN = your_telegram_bot_token_here
```

### Step 4 — Deploy
Railway will automatically build and start the bot.  
`nixpacks.toml` handles installing ffmpeg — no extra setup needed.

---

## ♻️ Updating the bot

```bash
git add .
git commit -m "describe what you changed"
git push
```
Railway redeploys automatically on every push.

---

## ⚠️ Notes

- **users_log.txt** is stored on Railway's ephemeral disk and will be lost on restarts.  
  For persistent logs, add a Railway Volume or use an external service.
- The bot token in your original code is now public — **revoke it via @BotFather** and generate a new one.
