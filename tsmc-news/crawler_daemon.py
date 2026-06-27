import urllib.request
import urllib.parse
import json
import re
import sys
import os
import ssl
import time
from datetime import datetime, timezone, timedelta

# Create SSL context to bypass SSL validation
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}

# Notification helpers removed

# 3. Fetch stock prices from Yahoo Finance
def fetch_stock_price(symbol):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1m&range=1d"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            if 'chart' in data and 'result' in data['chart'] and data['chart']['result']:
                meta = data['chart']['result'][0]['meta']
                price = meta.get('regularMarketPrice')
                prev_close = meta.get('previousClose')
                change = price - prev_close if price and prev_close else 0.0
                change_percent = (change / prev_close * 100.0) if prev_close else 0.0
                return {
                    "price": round(price, 2) if price else 0.0,
                    "change": round(change, 2),
                    "change_percent": round(change_percent, 2)
                }
    except Exception as e:
        print(f"Error fetching stock {symbol}: {e}")
    return {"price": 0.0, "change": 0.0, "change_percent": 0.0}

# 4. Fetch TSMC news from Anue API
def fetch_tsmc_news():
    news_items = []
    for q in ["台積電", "2330"]:
        q_encoded = urllib.parse.quote(q)
        url = f"https://ess.api.cnyes.com/ess/api/v1/news/keyword?q={q_encoded}&limit=20"
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
                if 'data' in data and 'items' in data['data']:
                    news_items.extend(data['data']['items'])
        except Exception as e:
            print(f"Error fetching news for q={q}: {e}")
            
    unique_news = {}
    for item in news_items:
        news_id = item.get('newsId')
        if news_id and news_id not in unique_news:
            unique_news[news_id] = item
            
    sorted_news = sorted(unique_news.values(), key=lambda x: x.get('publishAt', 0), reverse=True)
    return sorted_news

def run_crawl():
    tz_tw = timezone(timedelta(hours=8))
    now_tw = datetime.now(tz_tw)
    print(f"[{now_tw.strftime('%Y-%m-%d %H:%M:%S')}] Crawl started...")

    # Fetch stock prices
    tw_price = fetch_stock_price("2330.TW")
    us_price = fetch_stock_price("TSM")
    
    # Fetch news
    raw_news = fetch_tsmc_news()
    print(f"Fetched {len(raw_news)} unique news items.")
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(script_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    json_path = os.path.join(data_dir, "tsmc_news.json")
    subscribers_path = os.path.join(data_dir, "subscribers.json")
    
    # Load existing cached news (to check for duplicates / new items)
    existing_news_ids = set()
    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                cached_data = json.load(f)
                for item in cached_data.get("news", []):
                    existing_news_ids.add(item["news_id"])
        except Exception as e:
            print("Error loading cached news:", e)
            
    # Compile news list
    new_news_count = 0
    compiled_news = []
    for item in raw_news:
        news_id = item["newsId"]
        
        pub_ts = item.get("publishAt")
        pub_time_str = ""
        if pub_ts:
            dt = datetime.fromtimestamp(pub_ts, tz=timezone.utc).astimezone(tz_tw)
            pub_time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
            
        title = (item.get("title") or "").strip()
        summary = (item.get("summary") or "").strip()
        news_url = f"https://news.cnyes.com/news/id/{news_id}"
        
        compiled_news.append({
            "news_id": news_id,
            "title": title,
            "summary": summary,
            "publish_time": pub_time_str,
            "publish_timestamp": pub_ts,
            "url": news_url,
            "keywords": item.get("keywordForTag", [])
        })
        
        if len(existing_news_ids) > 0 and news_id not in existing_news_ids:
            new_news_count += 1
            print(f"🔥 New article detected [{news_id}]: {title}")
                
    # Sort by timestamp descending
    compiled_news = sorted(compiled_news, key=lambda x: x.get('publish_timestamp', 0), reverse=True)
    compiled_news = compiled_news[:100]

    # Save to file
    output_data = {
        "last_updated": now_tw.strftime("%Y-%m-%d %H:%M:%S"),
        "stock_prices": {
            "tw_2330": tw_price,
            "us_tsm": us_price
        },
        "news": compiled_news
    }
    
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
        
    print(f"Saved {len(compiled_news)} news items (new notified: {new_news_count}) to {json_path}")
    print("Crawl session successfully completed.")

if __name__ == "__main__":
    is_daemon = len(sys.argv) == 1 or sys.argv[1] == "daemon"
    
    if is_daemon:
        print("Starting TSMC News Crawler Daemon (polling every 60 seconds)...")
        while True:
            try:
                run_crawl()
            except Exception as e:
                print(f"Crawl session failed: {e}")
            time.sleep(60)
    else:
        run_crawl()
