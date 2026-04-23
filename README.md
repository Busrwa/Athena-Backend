# 🦉 Athena – AI Investment Assistant (Backend)

Django REST API powering Athena, a personal BIST stock investment assistant.
Scans 80 stocks, performs technical analysis, and generates AI-powered 
buy/sell signals using Groq (Llama 3.3 70B). Deployed on Render.

## ⚙️ Tech Stack
- Django + Django REST Framework
- Groq API (Llama 3.3 70B)
- Supabase PostgreSQL
- yfinance (15-min delayed data)
- Render deployment

## 💡 Features
- Scans 80 BIST stocks with RSI, MACD, Bollinger Bands, EMA analysis
- AI-powered portfolio recommendations with stop-loss/target prices
- Paper trading with backtesting
- Real-time market data (BIST100, USD/TRY, gold, crypto)
- KAP news RSS feed integration
- Email alerts for signals

## 🔗 Related
- Frontend: [Athena React Native App](https://github.com/Busrwa/Athena-Frontend)

## 🚀 Getting Started
```bash
git clone https://github.com/Busrwa/Athena-Backend.git
cd Athena-Backend
pip install -r requirements.txt
# Add .env: SECRET_KEY, DATABASE_URL, GROQ_API_KEY, SUPABASE_URL, SUPABASE_KEY
python manage.py migrate
python manage.py runserver
```

## ⚠️ Disclaimer
This API is for personal use only and does not constitute financial advice.
All investment decisions are the sole responsibility of the user.
Technical analysis is based on historical data and does not guarantee future results.

## 📄 License
MIT License — see LICENSE file for details.