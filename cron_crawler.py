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

def run():
    # 1. Determine Target Date (Taiwan Time UTC+8)
    tz_tw = timezone(timedelta(hours=8))
    now_tw = datetime.now(tz_tw)
    
    # If date is provided as first argument, use it. Otherwise use current date.
    if len(sys.argv) > 1:
        date_str = sys.argv[1] # Format: YYYYMMDD
    else:
        date_str = now_tw.strftime("%Y%m%d")
        
    year = int(date_str[0:4])
    month = date_str[4:6]
    day = date_str[6:8]
    formatted_date_dash = f"{year}-{month}-{day}"
    minguo_year = year - 1911
    minguo_date = f"{minguo_year}/{month}/{day}"
    
    print(f"Target Date: {formatted_date_dash} (Minguo: {minguo_date})")
    
    # Check-and-Skip: Check if history file already has today's date
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
            
    # Check if target date is already in history (unless running manually with override)
    if len(sys.argv) == 1:
        for entry in history_entries:
            if entry.get("date") == formatted_date_dash:
                print(f"Data for {formatted_date_dash} already exists in history. Skipping crawl.")
                sys.exit(0)

    # 2. Fetch TWSE BFI82U (三大法人買賣金額統計表)
    url_bfi = f"https://www.twse.com.tw/fund/BFI82U?response=json&dayDate={date_str}&type=day"
    print(f"Fetching TWSE BFI82U from {url_bfi}...")
    bfi_data = fetch_json(url_bfi)
    if not bfi_data or 'data' not in bfi_data or len(bfi_data['data']) == 0:
        print(f"No BFI82U data for {formatted_date_dash} yet. It may be a non-trading day or not published yet.")
        sys.exit(1) # Exit with error so script can retry later
        
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
        print("No T86 semiconductor data published yet.")
        if len(sys.argv) == 1:
            print("Exiting with status 1 to retry later.")
            sys.exit(1)
            
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
    
    current_json_file = os.path.join(data_dir, "daily_chips.json")
    with open(current_json_file, "w", encoding="utf-8") as f:
        json.dump(current_data, f, indent=2, ensure_ascii=False)
    print(f"Saved today's details to {current_json_file}")

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
        "tsmc_chips": current_data["tsmc_chips"]
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

if __name__ == "__main__":
    try:
        run()
    except Exception as ex:
        print(f"Execution failed with error: {ex}")
        sys.exit(1)
