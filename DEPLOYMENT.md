# 🚀 Pulse Orchestrator — Deployment Guide

This guide will help you move your Pulse Expense Orchestrator from your local machine to the cloud using industry-standard free hosting.

---

## 🏗️ Prerequisites
1. **GitHub Account**: To host your code.
2. **Supabase Project**: (Already created) — You need the `postgresql+asyncpg://...` URL.
3. **Telegram Bot Token**: From @BotFather.
4. **Gemini API Key**: From Google AI Studio.

---

## 📤 Step 1: GitHub Repository
1. Create a new repository on GitHub (Private is recommended to keep your code secure).
2. Open your terminal in the project folder and run:
   ```bash
   git init
   git add .
   git commit -m "Initial commit: Ready for production"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
   git push -u origin main
   ```
   *Note: Our `.dockerignore` and `.gitignore` will automatically prevent your local secrets (`.env`) and database (`data/`) from being uploaded.*

---

## 🤖 Step 2: Deploy the Bot (Render.com)
Render provides an incredibly stable free tier for Python Web Services.

1. **Sign up**: Go to [Render.com](https://render.com/).
2. **Create App**: Click **New** -> **Web Service**.
3. **Connect GitHub**: Choose your `pulse-orchestrator` repository.
4. **Settings**:
   - **Name**: `pulse-bot`
   - **Region**: Choose one closest to you (e.g., Frankfurt/Oregon).
   - **Branch**: `main`
   - **Runtime**: `Docker`
   - **Instance Type**: Free
5. **Environment Variables**: Add your secrets: 
   - `TELEGRAM_BOT_TOKEN`
   - `GEMINI_API_KEY`
   - `DATABASE_URL` (Use your Supabase connection string)
   - `DASHBOARD_URL`
6. **Deploy**: Click **Create Web Service**. Render will build the Docker container and start your bot.
7. **The "Keep-Alive" Hack**: 
   - Render's free tier sleeps after 15 minutes of inactivity.
   - Go to [cron-job.org](https://cron-job.org/) (free).
   - Create a cron job that pings your Render URL (e.g., `https://pulse-bot.onrender.com`) every 14 minutes. This guarantees your bot stays awake 24/7!

---

## 📊 Step 3: Deploy the Dashboard (Streamlit Cloud)
Streamlit Community Cloud is free forever for dashboard hosting.

1. **Sign up**: Go to [share.streamlit.io](https://share.streamlit.io/).
2. **New App**: Click **Create new app**.
3. **Settings**:
   - **Repository**: Select your GitHub repo.
   - **Main file path**: `dashboard.py`
4. **Advanced Settings (Secrets)**:
   Click **Advanced settings...** and paste the content of your `.env` file into the **Secrets** box. 
   *Note: Ensure `DATABASE_URL` is included here as well.*
5. **Deploy**: Click **Deploy!**. Once it finishes, copy the URL (e.g., `https://pulse-dash.streamlit.app`).

---

## 🔗 Step 4: Connecting the Two
Now that your dashboard has a real public URL, we need to tell the bot where it is.

1. Go back to your **Koyeb Dashboard**.
2. Find your **Service** -> **Settings** -> **Environment Variables**.
3. Update `DASHBOARD_URL` with your Streamlit link.
4. Save and Redeploy.

---

## ✅ Verification Checklist
- [ ] Send `/start` to your bot. It should reply instantly.
- [ ] Send `/dashboard` to get an OTP.
- [ ] Open the public Streamlit link on your phone.
- [ ] Log in using your ID and the OTP.
- [ ] **Success!** You now have a production-grade personal finance system.

---

## 🛠️ Maintenance & Updates
Whenever you want to update your app, simply push your changes to GitHub:
```bash
git add .
git commit -m "Cool new feature"
git push origin main
```
Both Koyeb and Streamlit will detect the change and **automatically rebuild** your app within minutes!
