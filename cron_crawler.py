import urllib.request
import json
import csv
import re
import sys
import os
import ssl
from datetime import datetime, timezone, timedelta

# Create SSL context to bypass SSL validation (some government/financial sites have certificates that python standard library might reject)
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}

def fetch_json(url):
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=15) as response:
            body = response.read().decode('utf-8')
            return json.loads(body)
    except Exception as e:
        print(f"Error fetching JSON from {url}: {e}")
        return None

def fetch_html(url):
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=15) as response:
            return response.read().decode('utf-8')
    except Exception as e:
        print(f"Error fetching HTML from {url}: {e}")
        return None

def parse_number(val):
    if not val:
        return 0
    # Strip commas, percentage signs, spaces
    val_clean = str(val).replace(',', '').replace('%', '').strip()
    try:
        if '.' in val_clean:
            return float(val_clean)
        return int(val_clean)
    except ValueError:
        return 0

def load_env():
    # Try script directory
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(env_path):
        # Try repository root (parent directory)
        env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
        
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f_env:
                for env_line in f_env:
                    env_line = env_line.strip()
                    if env_line and not env_line.startswith("#") and "=" in env_line:
                        k, v = env_line.split("=", 1)
                        os.environ[k.strip()] = v.strip().strip('"').strip("'")
            print(f"Loaded environment from {env_path}")
        except Exception as env_err:
            print(f"⚠️ 讀取 .env 失敗: {env_err}")

def generate_ai_summary(market_data):
    api_key = os.environ.get("gemini_api_key") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("⚠️ GEMINI_API_KEY not found in environment. Skipping AI summary.")
        return "無 AI 分析數據（請先於 .env 設定 gemini_api_key）"
        
    prompt = (
        f"你是專業的台灣股市分析助手。請根據以下這一天（{market_data['date']}）的三大法人籌碼數據，"
        f"寫一段 80-120 字的簡短專業分析（繁體中文），指出今天法人資金的動向重點（如外資是買是賣、投信態度、台積電籌碼、融資券增減等）。\n\n"
        f"【本日數據】：\n"
        f"- 大盤成交量：{market_data['trading_volume']['tse_volume']:.2f}億元\n"
        f"- 三大法人合計買賣超（集中+櫃買）：{market_data['market_summary']['combined']['total']:.2f}億元 "
        f"（外資：{market_data['market_summary']['combined']['foreign']:.2f}億元，"
        f"投信：{market_data['market_summary']['combined']['trust']:.2f}億元，"
        f"自營商：{market_data['market_summary']['combined']['dealer']:.2f}億元）\n"
        f"- 台積電（2330）法人買賣超：{market_data['tsmc_chips']['total']}張 "
        f"（外資：{market_data['tsmc_chips']['foreign']}張，投信：{market_data['tsmc_chips']['trust']}張）\n"
        f"- 官股買賣超：{market_data['gov_banks']['net_buy']:.2f}億元\n"
        f"- 融資增減：{market_data['margin_trading']['margin_balance_change']:.2f}億元\n"
        f"- 融券增減：{market_data['margin_trading']['short_balance_change']}張\n"
        f"請直接輸出分析，不要帶有任何標題或格式引導符。"
    )
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }
    
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            ai_text = res_data['candidates'][0]['content']['parts'][0]['text']
            return ai_text.strip()
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        return "AI 分析生成失敗"

def crawl_date(date_str, history_entries, data_dir, history_file, tz_tw):
    year = int(date_str[0:4])
    month = date_str[4:6]
    day = date_str[6:8]
    formatted_date_dash = f"{year}-{month}-{day}"
    minguo_year = year - 1911
    minguo_date = f"{minguo_year}/{month}/{day}"
    
    print(f"Target Date: {formatted_date_dash} (Minguo: {minguo_date})")

    # 2. Fetch TWSE BFI82U (三大法人買賣金額統計表)
    url_bfi = f"https://www.twse.com.tw/fund/BFI82U?response=json&dayDate={date_str}&type=day"
    print(f"Fetching TWSE BFI82U from {url_bfi}...")
    bfi_data = fetch_json(url_bfi)
    if not bfi_data or 'data' not in bfi_data or len(bfi_data['data']) == 0:
        print(f"No BFI82U data for {formatted_date_dash} yet. It may be a non-trading day or not published yet.")
        return False
        
    # Process BFI82U
    # Row 0: 自營商(自行買賣), Row 1: 自營商(避險), Row 2: 投信, Row 3: 外資及陸資
    # Format: [項目, 買進金額, 賣出金額, 買賣差額]
    tse_foreign = 0.0
    tse_trust = 0.0
    tse_dealer = 0.0
    
    for row in bfi_data['data']:
        item = row[0]
        net_val = parse_number(row[3]) / 100000000.0 # Convert to 億元
        if '外資及陸資(不含外資自營商)' in item or item.strip() == '外資及陸資':
            tse_foreign = net_val
        elif '投信' in item:
            tse_trust = net_val
        elif '自營商(自行買賣)' in item or '自營商(避險)' in item or '自營商合計' in item:
            tse_dealer += net_val
            
    tse_total = tse_foreign + tse_trust + tse_dealer
    print(f"TSE Summary: Foreign={tse_foreign:.2f}億, Trust={tse_trust:.2f}億, Dealer={tse_dealer:.2f}億, Total={tse_total:.2f}億")

    # 3. Fetch TPEx 三大法人買賣金額彙總表
    url_tpex = f"https://www.tpex.org.tw/web/stock/3insti/3insti_summary/3itrdsum_result.php?l=zh-tw&d={minguo_date}&o=json"
    print(f"Fetching TPEx from {url_tpex}...")
    tpex_data = fetch_json(url_tpex)
    
    otc_foreign = 0.0
    otc_trust = 0.0
    otc_dealer = 0.0
    
    if tpex_data and 'tables' in tpex_data and len(tpex_data['tables']) > 0:
        table_rows = tpex_data['tables'][0].get('data', [])
        for row in table_rows:
            item = row[0]
            net_val = parse_number(row[3]) / 100000000.0 # Convert to 億元
            if '外資及陸資合計' in item or '外資及陸資(不含自營商)' in item:
                otc_foreign = net_val
            elif '投信' in item:
                otc_trust = net_val
            elif '自營商(自行買賣)' in item or '自營商(避險)' in item or '自營商合計' in item:
                # Be careful not to double count if '自營商合計' and sub items are both in rows.
                # In TPEx:
                # Row 0: 外資及陸資合計
                # Row 3: 投信
                # Row 4: 自營商合計
                if '合計' in item and '三大法人合計' not in item and '外資' not in item:
                    otc_dealer = net_val
    else:
        print("Could not fetch TPEx summary. Proceeding with 0 values for OTC.")

    otc_total = otc_foreign + otc_trust + otc_dealer
    print(f"OTC Summary: Foreign={otc_foreign:.2f}億, Trust={otc_trust:.2f}億, Dealer={otc_dealer:.2f}億, Total={otc_total:.2f}億")

    # Combined Summary
    comb_foreign = tse_foreign + otc_foreign
    comb_trust = tse_trust + otc_trust
    comb_dealer = tse_dealer + otc_dealer
    comb_total = tse_total + otc_total

    # 4. Fetch TWSE MI_MARGN (信用交易統計 Table 0)
    url_marg = f"https://www.twse.com.tw/exchangeReport/MI_MARGN?response=json&date={date_str}&selectType=ALL"
    print(f"Fetching TWSE MI_MARGN from {url_marg}...")
    marg_data = fetch_json(url_marg)
    
    margin_balance_change = 0.0
    margin_balance_total = 0.0
    short_balance_change = 0
    short_balance_total = 0
    
    if marg_data and 'tables' in marg_data and len(marg_data['tables']) > 0:
        table0 = marg_data['tables'][0]
        table0_data = table0.get('data', [])
        # Row 0: 融資(交易單位), Row 1: 融券(交易單位), Row 2: 融資金額(仟元)
        if len(table0_data) >= 3:
            row_unit_short = table0_data[1] # 融券(交易單位)
            row_money_margin = table0_data[2] # 融資金額(仟元)
            
            # Financing changes (converted to 億元)
            margin_prev = parse_number(row_money_margin[4]) * 1000.0 / 100000000.0
            margin_curr = parse_number(row_money_margin[5]) * 1000.0 / 100000000.0
            margin_balance_total = margin_curr
            margin_balance_change = margin_curr - margin_prev
            
            # Short changes (sheets/trading units)
            short_prev = parse_number(row_unit_short[4])
            short_curr = parse_number(row_unit_short[5])
            short_balance_total = short_curr
            short_balance_change = short_curr - short_prev
            
            print(f"Margin Trading: Margin Change={margin_balance_change:.2f}億 (Total={margin_balance_total:.2f}億), Short Change={short_balance_change}張 (Total={short_balance_total}張)")
    else:
        print("Could not fetch Margin data.")

    # 5. Fetch TWSE FMTQIK (大盤成交值統計)
    url_fmt = f"https://www.twse.com.tw/exchangeReport/FMTQIK?response=json&date={date_str}"
    print(f"Fetching TWSE FMTQIK from {url_fmt}...")
    fmt_data = fetch_json(url_fmt)
    tse_volume = 0.0
    
    if fmt_data and 'data' in fmt_data and len(fmt_data['data']) > 0:
        # Last row in FMTQIK is today's volume (since FMTQIK returns data for the whole month up to today)
        today_fmt_row = None
        # Let's search the rows for the target date.
        # FMTQIK Date format in JSON is like "115/06/24" (Minguo format)
        for r in fmt_data['data']:
            if r[0] == minguo_date:
                today_fmt_row = r
                break
        
        if not today_fmt_row:
            # Fallback to the last row
            today_fmt_row = fmt_data['data'][-1]
            
        tse_volume = parse_number(today_fmt_row[2]) / 100000000.0 # Convert to 億元
        print(f"TSE Volume: {tse_volume:.2f} 億元 (Date matches: {today_fmt_row[0]})")
    else:
        print("Could not fetch FMTQIK volume data.")

    # 6. Fetch HiStock 八大官股
    url_histock = "https://histock.tw/stock/broker8.aspx"
    print(f"Fetching HiStock Eight Banks from {url_histock}...")
    histock_html = fetch_html(url_histock)
    
    gov_date_str = ""
    gov_net_buy = 0.0
    
    if histock_html:
        match_chart = re.search(r'loadChart\((.*?)\);', histock_html, re.DOTALL)
        if match_chart:
            try:
                chart_json = json.loads(match_chart.group(1))
                sum_money = json.loads(chart_json.get('SumMoney', '[]'))
                
                # Scan from end to find latest non-zero day
                for ts, val in reversed(sum_money):
                    if val != 0:
                        dt = datetime.fromtimestamp(ts / 1000.0, tz=timezone.utc).astimezone(tz_tw)
                        gov_date_str = dt.strftime("%Y-%m-%d")
                        gov_net_buy = float(val) # Already in 億元 on HiStock broker8.aspx chart!
                        break
                print(f"Government Bank: Latest available Net Buy={gov_net_buy:.2f}億 on {gov_date_str}")
            except Exception as chart_err:
                print(f"Error parsing HiStock loadChart data: {chart_err}")
        else:
            print("Could not find loadChart function in HiStock HTML.")
    else:
        print("Could not fetch HiStock government banks page.")

    # 7. Fetch Top 10 Rankings
    # TWT38U (外資買賣超個股)
    url_twt38 = f"https://www.twse.com.tw/fund/TWT38U?response=json&date={date_str}"
    print(f"Fetching Foreign rankings from {url_twt38}...")
    twt38_data = fetch_json(url_twt38)
    
    foreign_buy_rankings = []
    foreign_sell_rankings = []
    
    if twt38_data and 'data' in twt38_data:
        # Col 1: 代號, Col 2: 名稱, Col 5: 買賣超股數
        stocks_list = []
        for row in twt38_data['data']:
            code = row[1].strip()
            name = row[2].strip()
            shares = parse_number(row[5])
            sheets = int(shares / 1000)
            stocks_list.append({"code": code, "name": name, "volume": sheets})
            
        # Sort descending for buy rankings
        stocks_sorted = sorted(stocks_list, key=lambda x: x['volume'], reverse=True)
        foreign_buy = [s for s in stocks_sorted if s['volume'] > 0]
        foreign_sell = [s for s in stocks_sorted if s['volume'] < 0]
        
        # Take top 10
        for i, s in enumerate(foreign_buy[:10]):
            foreign_buy_rankings.append({"rank": i+1, "code": s['code'], "name": s['name'], "volume": s['volume']})
        # For sell, we reverse volume so it's positive for display (or keep negative, let's make it positive/absolute sheet value, or keep negative. The index.html layout says "賣超張數" so absolute sheets value is better!)
        foreign_sell_sorted = sorted(foreign_sell, key=lambda x: x['volume']) # Ascending (most negative first)
        for i, s in enumerate(foreign_sell_sorted[:10]):
            foreign_sell_rankings.append({"rank": i+1, "code": s['code'], "name": s['name'], "volume": abs(s['volume'])})
            
        print(f"Foreign Rankings: Buy Top 1={foreign_buy_rankings[0] if len(foreign_buy_rankings) > 0 else 'None'}, Sell Top 1={foreign_sell_rankings[0] if len(foreign_sell_rankings) > 0 else 'None'}")
    else:
        print("Could not fetch Foreign stock rankings.")

    # TWT44U (投信買賣超個股)
    url_twt44 = f"https://www.twse.com.tw/fund/TWT44U?response=json&date={date_str}"
    print(f"Fetching Mutual Fund rankings from {url_twt44}...")
    twt44_data = fetch_json(url_twt44)
    
    trust_buy_rankings = []
    trust_sell_rankings = []
    
    if twt44_data and 'data' in twt44_data:
        # Col 1: 代號, Col 2: 名稱, Col 5: 買賣超股數
        stocks_list = []
        for row in twt44_data['data']:
            code = row[1].strip()
            name = row[2].strip()
            shares = parse_number(row[5])
            sheets = int(shares / 1000)
            stocks_list.append({"code": code, "name": name, "volume": sheets})
            
        # Sort descending
        stocks_sorted = sorted(stocks_list, key=lambda x: x['volume'], reverse=True)
        trust_buy = [s for s in stocks_sorted if s['volume'] > 0]
        trust_sell = [s for s in stocks_sorted if s['volume'] < 0]
        
        # Take top 10
        for i, s in enumerate(trust_buy[:10]):
            trust_buy_rankings.append({"rank": i+1, "code": s['code'], "name": s['name'], "volume": s['volume']})
        trust_sell_sorted = sorted(trust_sell, key=lambda x: x['volume']) # Ascending (most negative first)
        for i, s in enumerate(trust_sell_sorted[:10]):
            trust_sell_rankings.append({"rank": i+1, "code": s['code'], "name": s['name'], "volume": abs(s['volume'])})
            
        print(f"Trust Rankings: Buy Top 1={trust_buy_rankings[0] if len(trust_buy_rankings) > 0 else 'None'}, Sell Top 1={trust_sell_rankings[0] if len(trust_sell_rankings) > 0 else 'None'}")
    else:
        print("Could not fetch Mutual Fund stock rankings.")

    # 7.5 Fetch TSMC (2330) individual institutional buy/sell (T86)
    url_tsmc_t86 = f"https://www.twse.com.tw/fund/T86?response=json&date={date_str}&selectType=24"
    print(f"Fetching TSMC institutional data from {url_tsmc_t86}...")
    t86_data = fetch_json(url_tsmc_t86)
    
    if not t86_data or 'data' not in t86_data or len(t86_data['data']) == 0:
        print("No T86 semiconductor data published yet. Skipping this date.")
        return False
            
    tsmc_foreign = 0
    tsmc_trust = 0
    tsmc_dealer = 0
    tsmc_total = 0
    
    if t86_data and 'data' in t86_data:
        for row in t86_data['data']:
            if row[0].strip() == '2330':
                tsmc_foreign = int(parse_number(row[4]) / 1000)
                tsmc_trust = int(parse_number(row[10]) / 1000)
                tsmc_dealer = int(parse_number(row[11]) / 1000)
                tsmc_total = int(parse_number(row[18]) / 1000)
                print(f"TSMC (2330) Chips Lots: Foreign={tsmc_foreign}, Trust={tsmc_trust}, Dealer={tsmc_dealer}, Total={tsmc_total}")
                break

    # 8. Save Current Day JSON
    current_data = {
        "date": formatted_date_dash,
        "updated_time": datetime.now(tz_tw).strftime("%Y-%m-%d %H:%M:%S"),
        "tsmc_chips": {
            "foreign": tsmc_foreign,
            "trust": tsmc_trust,
            "dealer": tsmc_dealer,
            "total": tsmc_total
        },
        "market_summary": {
            "tse": {
                "foreign": round(tse_foreign, 2),
                "trust": round(tse_trust, 2),
                "dealer": round(tse_dealer, 2),
                "total": round(tse_total, 2)
            },
            "tpex": {
                "foreign": round(otc_foreign, 2),
                "trust": round(otc_trust, 2),
                "dealer": round(otc_dealer, 2),
                "total": round(otc_total, 2)
            },
            "combined": {
                "foreign": round(comb_foreign, 2),
                "trust": round(comb_trust, 2),
                "dealer": round(comb_dealer, 2),
                "total": round(comb_total, 2)
            }
        },
        "gov_banks": {
            "net_buy": round(gov_net_buy, 2),
            "date": gov_date_str
        },
        "margin_trading": {
            "margin_balance_change": round(margin_balance_change, 2),
            "margin_balance_total": round(margin_balance_total, 2),
            "short_balance_change": int(short_balance_change),
            "short_balance_total": int(short_balance_total)
        },
        "trading_volume": {
            "tse_volume": round(tse_volume, 2)
        },
        "rankings": {
            "foreign_buy": foreign_buy_rankings,
            "foreign_sell": foreign_sell_rankings,
            "trust_buy": trust_buy_rankings,
            "trust_sell": trust_sell_rankings
        }
    }
    # 7.8 Generate AI Summary
    ai_summary = generate_ai_summary(current_data)
    current_data["ai_summary"] = ai_summary
    
    current_json_file = os.path.join(data_dir, "daily_chips.json")
    with open(current_json_file, "w", encoding="utf-8") as f:
        json.dump(current_data, f, indent=2, ensure_ascii=False)
    print(f"Saved today's details to {current_json_file}")
    
    # 7.9 Update rankings history and calculate buying streaks
    update_rankings_history_and_calculate_streaks(current_data, data_dir)

    # 9. Update History JSON
    # Remove existing entry for today if we are overwriting it
    history_entries = [entry for entry in history_entries if entry.get("date") != formatted_date_dash]
    
    # Add new entry
    history_entry = {
        "date": formatted_date_dash,
        "tse_summary": current_data["market_summary"]["tse"],
        "tpex_summary": current_data["market_summary"]["tpex"],
        "combined_summary": current_data["market_summary"]["combined"],
        "gov_banks": current_data["gov_banks"],
        "margin_trading": current_data["margin_trading"],
        "trading_volume": current_data["trading_volume"],
        "tsmc_chips": current_data["tsmc_chips"],
        "ai_summary": ai_summary
    }
    history_entries.append(history_entry)
    
    # Sort history entries by date ascending
    history_entries = sorted(history_entries, key=lambda x: x["date"])
    
    history_data = {
        "last_updated": datetime.now(tz_tw).strftime("%Y-%m-%d %H:%M:%S"),
        "history": history_entries
    }
    
    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(history_data, f, indent=2, ensure_ascii=False)
    print(f"Saved history file with {len(history_entries)} entries to {history_file}")

    # 10. Generate Today's CSV File
    csv_file = os.path.join(data_dir, "daily_chips.csv")
    with open(csv_file, "w", encoding="utf-8-sig", newline="") as f: # Use utf-8-sig so Excel opens Chinese characters correctly
        writer = csv.writer(f)
        writer.writerow(["台股法人籌碼盤後數據彙整報告"])
        writer.writerow(["資料日期", formatted_date_dash])
        writer.writerow(["更新時間 (台灣)", current_data["updated_time"]])
        writer.writerow([])
        writer.writerow(["市場統計指標", "本日數據"])
        writer.writerow(["大盤成交金額 (億元)", f"{tse_volume:.2f}"])
        writer.writerow(["融資餘額增減 (億元)", f"{margin_balance_change:.2f} (目前總額: {margin_balance_total:.2f})"])
        writer.writerow(["融券餘額增減 (張)", f"{short_balance_change} (目前總張: {short_balance_total})"])
        writer.writerow(["八大官股買賣超 (億元)", f"{gov_net_buy:.2f} (統計日期: {gov_date_str})"])
        writer.writerow([])
        writer.writerow(["台積電 (2330) 三大法人買賣超 (單位: 張)"])
        writer.writerow(["外資買賣超", f"{tsmc_foreign}"])
        writer.writerow(["投信買賣超", f"{tsmc_trust}"])
        writer.writerow(["自營商買賣超", f"{tsmc_dealer}"])
        writer.writerow(["三大法人合計", f"{tsmc_total}"])
        writer.writerow([])
        writer.writerow(["三大法人買賣超金額統計 (單位: 億元)"])
        writer.writerow(["市場", "外資及陸資", "投信", "自營商", "合計"])
        writer.writerow(["集中市場 (TSE)", f"{tse_foreign:.2f}", f"{tse_trust:.2f}", f"{tse_dealer:.2f}", f"{tse_total:.2f}"])
        writer.writerow(["櫃買市場 (OTC)", f"{otc_foreign:.2f}", f"{otc_trust:.2f}", f"{otc_dealer:.2f}", f"{otc_total:.2f}"])
        writer.writerow(["市場合計 (TSE+OTC)", f"{comb_foreign:.2f}", f"{comb_trust:.2f}", f"{comb_dealer:.2f}", f"{comb_total:.2f}"])
        writer.writerow([])
        
        # Rankings Row
        writer.writerow(["外資及陸資個股買賣超排行 Top 10 (單位: 張)"])
        writer.writerow(["排名", "買超代號", "買超名稱", "買超張數", "賣超代號", "賣超名稱", "賣超張數"])
        for i in range(10):
            buy_row = foreign_buy_rankings[i] if i < len(foreign_buy_rankings) else {"code": "", "name": "", "volume": ""}
            sell_row = foreign_sell_rankings[i] if i < len(foreign_sell_rankings) else {"code": "", "name": "", "volume": ""}
            writer.writerow([i+1, buy_row["code"], buy_row["name"], buy_row["volume"], sell_row["code"], sell_row["name"], sell_row["volume"]])
        writer.writerow([])
        
        writer.writerow(["投信個股買賣超排行 Top 10 (單位: 張)"])
        writer.writerow(["排名", "買超代號", "買超名稱", "買超張數", "賣超代號", "賣超名稱", "賣超張數"])
        for i in range(10):
            buy_row = trust_buy_rankings[i] if i < len(trust_buy_rankings) else {"code": "", "name": "", "volume": ""}
            sell_row = trust_sell_rankings[i] if i < len(trust_sell_rankings) else {"code": "", "name": "", "volume": ""}
            writer.writerow([i+1, buy_row["code"], buy_row["name"], buy_row["volume"], sell_row["code"], sell_row["name"], sell_row["volume"]])
            
    print(f"Generated CSV report at {csv_file}")
    print("All tasks completed successfully!")
    return True

def update_rankings_history_and_calculate_streaks(current_data, data_dir):
    history_file = os.path.join(data_dir, "rankings_history.json")
    
    # 1. 載入已存檔的排行歷史記錄
    rankings_history = []
    if os.path.exists(history_file):
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                rankings_history = json.load(f)
        except Exception as e:
            print(f"Error loading rankings history: {e}")
            
    # 2. 加入今日最新排行個股代號
    today_entry = {
        "date": current_data["date"],
        "foreign_buy": [item["code"] for item in current_data["rankings"]["foreign_buy"]],
        "foreign_sell": [item["code"] for item in current_data["rankings"]["foreign_sell"]],
        "trust_buy": [item["code"] for item in current_data["rankings"]["trust_buy"]],
        "trust_sell": [item["code"] for item in current_data["rankings"]["trust_sell"]]
    }
    
    # 避免重複日期
    rankings_history = [entry for entry in rankings_history if entry["date"] != today_entry["date"]]
    rankings_history.append(today_entry)
    
    # 僅保留最近 5 天的歷史
    rankings_history = sorted(rankings_history, key=lambda x: x["date"])[-5:]
    
    try:
        with open(history_file, "w", encoding="utf-8") as f:
            json.dump(rankings_history, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving rankings history: {e}")
        
    # 3. 計算連續買超的個股天數
    consecutive_data = {
        "date": current_data["date"],
        "foreign_buy_streak_3d": [],
        "foreign_buy_streak_2d": [],
        "trust_buy_streak_3d": [],
        "trust_buy_streak_2d": []
    }
    
    # 至少要有兩天的數據才能計算連續買超
    if len(rankings_history) >= 2:
        today_rankings = rankings_history[-1]
        
        def calculate_streak(ranking_key):
            streaks = {}
            today_codes = today_rankings[ranking_key]
            for code in today_codes:
                name = ""
                origin_key = "foreign_buy" if "foreign" in ranking_key else "trust_buy"
                for item in current_data["rankings"][origin_key]:
                    if item["code"] == code:
                        name = item["name"]
                        break
                
                streak_count = 1
                for day_idx in range(len(rankings_history) - 2, -1, -1):
                    prev_day = rankings_history[day_idx]
                    if code in prev_day[ranking_key]:
                        streak_count += 1
                    else:
                        break # 連續中斷
                
                if streak_count >= 2:
                    streaks[code] = {
                        "code": code,
                        "name": name,
                        "streak": streak_count
                    }
            return streaks
            
        foreign_streaks = calculate_streak("foreign_buy")
        trust_streaks = calculate_streak("trust_buy")
        
        # 分組：連續 3 天（及以上）與連續 2 天
        for code, info in foreign_streaks.items():
            if info["streak"] >= 3:
                consecutive_data["foreign_buy_streak_3d"].append(info)
            else:
                consecutive_data["foreign_buy_streak_2d"].append(info)
                
        for code, info in trust_streaks.items():
            if info["streak"] >= 3:
                consecutive_data["trust_buy_streak_3d"].append(info)
            else:
                consecutive_data["trust_buy_streak_2d"].append(info)
                
    # 存檔至 consecutive_buys.json
    consecutive_file = os.path.join(data_dir, "consecutive_buys.json")
    try:
        with open(consecutive_file, "w", encoding="utf-8") as f:
            json.dump(consecutive_data, f, indent=2, ensure_ascii=False)
        print(f"Successfully calculated and saved consecutive buys to {consecutive_file}")
    except Exception as e:
        print(f"Error saving consecutive buys: {e}")

def run():
    load_env()
    import time
    tz_tw = timezone(timedelta(hours=8))
    now_tw = datetime.now(tz_tw)
    
    # Generate list of target dates to check
    target_dates = []
    if len(sys.argv) > 1:
        target_dates = [sys.argv[1]]
    else:
        # Check last 7 days to backfill any missing weekdays!
        for i in range(7):
            d = now_tw - timedelta(days=i)
            if d.weekday() < 5:
                target_dates.append(d.strftime("%Y%m%d"))
        target_dates.sort()  # Sort older dates first!
        
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(script_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    history_file = os.path.join(data_dir, "daily_chips_history.json")
    
    history_entries = []
    if os.path.exists(history_file):
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                history_data = json.load(f)
                history_entries = history_data.get("history", [])
        except Exception as e:
            print(f"Error loading history file: {e}")
            
    crawled_any = False
    for date_str in target_dates:
        year = int(date_str[0:4])
        month = date_str[4:6]
        day = date_str[6:8]
        formatted_date_dash = f"{year}-{month}-{day}"
        
        # Skip if already exists in history (unless running manually with arguments)
        if len(sys.argv) == 1:
            already_exists = False
            for entry in history_entries:
                if entry.get("date") == formatted_date_dash:
                    already_exists = True
                    break
            if already_exists:
                print(f"Data for {formatted_date_dash} already exists in history. Skipping backfill.")
                continue
                
        print(f"⚡ Processing Date: {formatted_date_dash} ...")
        try:
            success = crawl_date(date_str, history_entries, data_dir, history_file, tz_tw)
            if success:
                crawled_any = True
                # Reload history entries to keep it updated for the next date in loop!
                if os.path.exists(history_file):
                    with open(history_file, "r", encoding="utf-8") as f:
                        history_data = json.load(f)
                        history_entries = history_data.get("history", [])
                time.sleep(3) # Polite crawl gap
        except Exception as date_ex:
            print(f"❌ Failed to crawl date {formatted_date_dash}: {date_ex}")
            
    if crawled_any:
        print("🎉 Crawl and backfill session successfully completed!")

if __name__ == "__main__":
    import traceback
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(script_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    status_file = os.path.join(data_dir, "crawler_status.json")
    
    try:
        run()
        status_data = {
            "last_run": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S"),
            "status": "success",
            "message": "Crawl session successfully completed."
        }
        with open(status_file, "w", encoding="utf-8") as sf:
            json.dump(status_data, sf, indent=2, ensure_ascii=False)
    except Exception as ex:
        err_msg = traceback.format_exc()
        print(f"Execution failed with error: {ex}")
        status_data = {
            "last_run": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S"),
            "status": "failed",
            "message": str(ex),
            "traceback": err_msg
        }
        with open(status_file, "w", encoding="utf-8") as sf:
            json.dump(status_data, sf, indent=2, ensure_ascii=False)
        sys.exit(1)
