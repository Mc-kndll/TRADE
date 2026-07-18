# TRADE — IBKR TWS Paper-Trading Bot

Windows üzerinde `ib-insync` ile IBKR Trader Workstation (TWS) paper hesabına bağlanan,
modüler ve güvenlik odaklı Python uygulaması. Yalnızca long sinyaller üretir; varsayılan
ayarlar emir iletimini kapalı tutar.

> Bu yazılım yatırım tavsiyesi değildir. Gerçek para ile kullanım için tasarlanmamıştır.

## Güvenlik varsayılanları

`.env.example` içindeki aşağıdaki değerler değiştirilmeden gelir:

```env
PAPER_ACCOUNT_ONLY=true
DRY_RUN=true
AUTO_TRADING_ENABLED=false
IB_PORT=7497
```

`PAPER_ACCOUNT_ONLY=true` iken uygulama yalnızca `DU...` ile başlayan IBKR paper hesabını
seçer ve farklı bir portu reddeder. Emir gönderilmesi için `DRY_RUN=false` ve
`AUTO_TRADING_ENABLED=true` değerlerinin birlikte, bilinçli olarak ayarlanması gerekir.
Canlı hesap desteği bu projenin güvenli çalışma kapsamı dışındadır.

## Özellikler

- TWS `127.0.0.1:7497` bağlantısı ve otomatik yeniden bağlanma
- EMA 9/20/50 trendi, RSI, MACD, VWAP, hacim ve yapılandırılabilir sinyal puanı
- ATR stop-loss, risk bütçesi ve maksimum pozisyon değeri ile adet hesabı
- Market veya limit parent; take-profit ve stop-loss çocuklarından oluşan bracket emir
- Parent/target/stop için güvenli `transmit=False/False/True` sırası
- Günlük zarar, açık pozisyon, duplicate sembol, RTH/holiday ve kill-switch kontrolleri
- Sinyal, emir, fill, hata ve hesap snapshot kayıtları için SQLite
- Telegram başlangıç/sinyal/emir/hata bildirimleri ve `/status`, `/positions`, `/stop`
- 09:35 ET ilk izleme, 09:45 ilk uygun giriş ve 10 dakikalık Telegram tarama raporları
- `--once`, sürekli çalışma ve bağlantısız yerel `--status` CLI modları

## Windows kurulumu

Python 3.11 veya 3.12 ve güncel IBKR TWS kurulu olmalıdır.

```powershell
git clone https://github.com/Mc-kndll/TRADE.git
cd TRADE
py -3.12 -m venv .venv
Set-ExecutionPolicy -Scope Process Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
notepad .env
```

Token, hesap numarası ve `.env` dosyasını Git’e eklemeyin.

## TWS paper hesabı ayarları

Paper Trading oturumunda TWS’yi açın. Ardından:

1. `Edit > Global Configuration > API > Settings` menüsüne gidin.
2. **Enable ActiveX and Socket Clients** seçeneğini açın.
3. Socket portunu **7497** yapın.
4. **Read-Only API** seçeneğini ilk bağlantı testlerinde açık tutabilirsiniz. Paper emir
   testi yapacağınız zaman kapatmanız gerekir.
5. Trusted IP listesine `127.0.0.1` ekleyin.
6. TWS’nin API bağlantı uyarısını onaylayın ve market-data aboneliklerinizi doğrulayın.

## Çalıştırma

Önce `.env` güvenli varsayılanlarıyla tek tur çalıştırın:

```powershell
python -m tradebot.main --once
```

Sürekli tarama:

```powershell
python -m tradebot.main
```

Varsayılan sürekli çalışma programı New York saatine göre `09:35, 09:45, 09:55...`
şeklindedir. `09:35` turu yalnızca gözlem ve rapordur; yeni emirler `09:45–15:00`
arasında değerlendirilebilir. Son rapor `15:55` saatindedir. Program `.env` içindeki
`SCAN_START_TIME`, `ORDER_START_TIME`, `LAST_ENTRY_TIME`, `SCAN_END_TIME` ve
`SCAN_INTERVAL_SECONDS` değerleriyle değiştirilebilir.

TWS bağlantısı kurmadan son yerel veritabanı durumunu görüntüleme:

```powershell
python -m tradebot.main --status
```

Ayrıca `python -m tradebot` aynı sürekli çalışma giriş noktasını sağlar. Loglar varsayılan
olarak `logs/tradebot.log`, SQLite veritabanı `tradebot.db` yoluna yazılır.

## Paper otomasyonunu açma

Yalnızca dry-run sonuçlarını ve TWS paper hesabını doğruladıktan sonra `.env` içinde:

```env
PAPER_ACCOUNT_ONLY=true
IB_PORT=7497
DRY_RUN=false
AUTO_TRADING_ENABLED=true
```

Bu değişiklik gerçek hesap kullanımına izin vermez; `DU...` paper hesabı kontrolü devam eder.
Kill switch için çalışan süreçte `Ctrl+C` kullanın veya yetkili Telegram chat’inden `/stop`
gönderin. Kill switch yeni emirleri engeller ve sürekli döngüyü sonlandırır.

## Telegram

BotFather üzerinden bot oluşturup `.env` içine `TELEGRAM_BOT_TOKEN` ve yalnızca komut kabul
edilecek `TELEGRAM_CHAT_ID` değerlerini yazın. Farklı chat kimliklerinden gelen komutlar
yok sayılır. `SEND_SCAN_REPORTS=true` olduğunda her planlı taramadan sonra saat, net
likidite, açık sembol sayısı, BUY sinyalleri ve güvenlik modu Telegram'a gönderilir.

## Geliştirme ve doğrulama

```powershell
python -m pytest
python -m ruff check .
python -m compileall -q tradebot tests
```

GitHub Actions aynı kontrolleri Windows üzerinde Python 3.11 ve 3.12 ile çalıştırır.
