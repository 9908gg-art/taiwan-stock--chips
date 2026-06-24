# 🔬 台積電新聞與股價即時追蹤器 (TSMC NewsRadar)

這是一個專為台積電 (2330.TW / TSM US) 投資者開發的 **即時新聞追蹤與推播訂閱面板**。系統每隔 1 分鐘會自動抓取最新的中文財經新聞，並在頂部即時呈現台灣與美國 ADR 兩地的最新股價與漲跌行情。當偵測到有新消息發布時，會自動透過電子郵件或 Telegram 發送通知給所有訂閱者。

---

## 🚀 系統功能與特色

1. **台美股價即時對照**：
   - **台股 (2330.TW)**：採用台股色彩規範（▲紅色上漲，▼綠色下跌）。
   - **美股 ADR (TSM)**：採用美股色彩規範（+綠色上漲，-紅色下跌）。
2. **每 1 分鐘自動同步**：後端守護進程自動執行定時排程，隨時抓取最新財經頭條。
3. **即時新聞推播訂閱**：
   - **電子郵件 (Email) 通知**：當新新聞發布時，將其標題與原文連結自動寄信通知。
   - **Telegram 即時推播**：透過 Telegram Bot 自動將最新新聞推播至訂閱者的 Chat ID。
4. **訂閱清單自動同步 GitHub**：
   - 使用者在網頁輸入訂閱資訊後，本地伺服器會自動將資料儲存至 `data/subscribers.json`，並自動執行 `git commit` 與 `git push` 同步回您的 GitHub 倉庫備份！
5. **展開/收合新聞大綱**：整合下拉摺疊功能，無須離開頁面即可閱讀新聞摘要。
6. **一鍵啟動整合包**：啟動後會自動開啟瀏覽器，非常適合部署在個人電腦或雲端伺服器。

---

## ⚙️ 快速使用與啟動步驟

### 第一步：進入目錄
確保您已在終端機進入該專案資料夾：
```bash
cd /root/tsmc-news-dashboard
```

### 第二步：配置環境變數 (選用)
為了讓系統能成功發送電子郵件與 Telegram 通知，請在啟動前設置對應的環境變數：

#### 1. 設定 Telegram 推播 (Bot)
* 在 Telegram 上搜尋 `@BotFather` 創建一個機器人以獲取 `TELEGRAM_BOT_TOKEN`。
* 使用者只需在網頁輸入他們的 Chat ID (可向 `@userinfobot` 獲取) 即可訂閱。
```bash
export TELEGRAM_BOT_TOKEN="您的_Telegram_Bot_Token"
```

#### 2. 設定 Email 發信伺服器 (SMTP)
* 設定您的發信信箱 (例如 Gmail 應用程式密碼或 SendGrid 等)。
```bash
export SMTP_SERVER="smtp.gmail.com"
export SMTP_PORT="587"
export SMTP_USER="您的寄信信箱@gmail.com"
export SMTP_PASSWORD="您的應用程式密碼"
```

### 第三步：一鍵啟動
執行一鍵啟動腳本，系統會自動同步數據，開啟本地網頁伺服器（預設 Port `8000`），並在 1.5 秒後**自動開啟您的網頁瀏覽器**展示面板：
```bash
python3 start_dashboard.py
```
*(如果 Port 8000 被佔用，系統會自動順延至 8001, 8002...)*

---

## ⚖️ 數據來源聲明
* 鉅亨網即時新聞 (cnyes.com)
* Yahoo Finance 即時股價
