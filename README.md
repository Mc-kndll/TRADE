# TRADE — IBKR Paper Trading Bot

Windows + Trader Workstation (TWS) üzerinde çalışan otomatik **paper trading** uygulaması.

> Bu yazılım yatırım tavsiyesi değildir. Varsayılan olarak yalnızca IBKR paper hesabına bağlanır ve canlı hesapta emir göndermeyi engeller.

## İlk sürüm

- IBKR TWS bağlantısı (`ib_async`)
- 10 dakikalık mumlarla EMA / RSI / MACD / ATR sinyali
- Risk bazlı pozisyon büyüklüğü
- Bracket order: giriş + stop-loss + take-profit
- Günlük zarar limiti ve açık pozisyon limiti
- Telegram bildirimleri
- SQLite işlem kayıtları
- `DRY_RUN` ve tam otomatik paper modu

## Windows kurulumu

1. Python 3.11 veya 3.12 kurulu olmalı.
2. TWS Paper hesabında oturum açın.
3. TWS: `Edit > Global Configuration > API > Settings`
   - Enable ActiveX and Socket Clients: açık
   - Socket port: `7497`
   - Read-Only API: kapalı (otomatik paper emirleri için)
   - Trusted IP: `127.0.0.1`
4. PowerShell:

```powershell
git clone https://github.com/Mc-kndll/TRADE.git
cd TRADE
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
Copy-Item .env.example .env
notepad .env
python -m tradebot
```

## Güvenli başlangıç

İlk testte `.env` içinde:

```env
DRY_RUN=true
AUTO_TRADING_ENABLED=false
```

Bağlantı, mum verisi ve sinyaller doğru çalıştıktan sonra paper otomasyonu için:

```env
DRY_RUN=false
AUTO_TRADING_ENABLED=true
PAPER_ACCOUNT_ONLY=true
```

## Telegram

`.env` içine bot token ve chat ID girin. Token hiçbir zaman GitHub'a yüklenmemelidir.

## Çalıştırma

```powershell
python -m tradebot
```

Tek tur test:

```powershell
python -m tradebot --once
```

## İzleme listesi

Varsayılan: `ARM,NVDA,AMD,TSLA,META,AAPL,MSFT,AMZN,QQQ,SPY`

Ayarlar `.env` dosyasından değiştirilebilir.
