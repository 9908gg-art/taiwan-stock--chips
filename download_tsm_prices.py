#!/usr/bin/env python3
import urllib.request
import json
import csv
import os
import sys
from datetime import datetime, timezone, timedelta

def download_tsm_data():
    symbol = "TSM"
    # Unofficial Yahoo Finance API for live market chart data
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1m&range=1d"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }
    
    print(f"正在從 Yahoo Finance 獲取 TSM (台積電 ADR) 即時數據...")
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            if 'chart' in data and 'result' in data['chart'] and data['chart']['result']:
                result = data['chart']['result'][0]
                meta = result['meta']
                
                # Extract key metrics
                price = meta.get('regularMarketPrice')
                prev_close = meta.get('previousClose')
                open_price = meta.get('regularMarketOpen') or price
                high = meta.get('chartPreviousClose') or price # Fallback
                low = meta.get('chartPreviousClose') or price
                volume = meta.get('regularMarketVolume') or 0
                
                # Calculate change
                change = price - prev_close if price and prev_close else 0.0
                change_percent = (change / prev_close * 100.0) if prev_close else 0.0
                
                # Fetch intraday high/low from indicators if available
                indicators = result.get('indicators', {})
                quote = indicators.get('quote', [{}])[0]
                highs = [h for h in quote.get('high', []) if h is not None]
                lows = [l for l in quote.get('low', []) if l is not None]
                if highs: high = max(highs)
                if lows: low = min(lows)
                
                # Time conversion (Taiwan Time UTC+8)
                tz_tw = timezone(timedelta(hours=8))
                now_tw = datetime.now(tz_tw)
                time_str = now_tw.strftime("%Y-%m-%d %H:%M:%S")
                
                # Save to CSV
                csv_filename = "tsm_live_price.csv"
                file_exists = os.path.exists(csv_filename)
                
                with open(csv_filename, "w", encoding="utf-8-sig", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(["商品代號", "即時價格", "漲跌金額", "漲跌幅(%)", "開盤價", "最高價", "最低價", "成交量", "更新時間(台灣)"])
                    writer.writerow([symbol, f"{price:.2f}", f"{change:+.2f}", f"{change_percent:+.2f}%", f"{open_price:.2f}", f"{high:.2f}", f"{low:.2f}", f"{volume:,}", time_str])
                
                print(f"🎉 數據獲取成功！已存檔至 {os.path.abspath(csv_filename)}")
                print(f"📈 TSM 目前價格: ${price:.2f} ({change:+.2f} / {change_percent:+.2f}%) | 時間: {time_str}")
            else:
                print("❌ 數據解析錯誤：未找到符合的資料結構。")
    except Exception as e:
        print(f"❌ 獲取資料失敗: {e}")

if __name__ == "__main__":
    download_tsm_data()
