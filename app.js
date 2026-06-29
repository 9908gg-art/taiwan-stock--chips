/* ==========================================================================
   台股法人籌碼下載器 - 互動邏輯與資料加載 (app.js)
   ========================================================================== */

document.addEventListener("DOMContentLoaded", () => {
    // 1. 初始化 Tab 切換功能
    initTabSwitches();

    // 2. 自伺服器/本地 JSON 載入資料
    loadChipsData();
});

/**
 * 初始化 Tab 切換功能
 */
function initTabSwitches() {
    const tabButtons = document.querySelectorAll(".tab-btn");
    const tabContents = document.querySelectorAll(".tab-content");

    tabButtons.forEach(button => {
        button.addEventListener("click", () => {
            const targetTab = button.getAttribute("data-tab");

            // 移除所有按鈕的 active 樣式
            tabButtons.forEach(btn => btn.classList.remove("active"));
            // 隱藏所有內容
            tabContents.forEach(content => content.classList.remove("active"));

            // 啟動當前點選的 Tab
            button.classList.add("active");
            document.getElementById(targetTab).classList.add("active");
        });
    });
}

/**
 * 格式化買賣差額數值
 * @param {number} value - 金額 (億元)
 * @param {string} unit - 單位 (預設為 '億')
 * @returns {string} 格式化後的字串，帶有正負號
 */
function formatNetValue(value, unit = " 億") {
    if (value > 0) {
        return `+${value.toFixed(2)}${unit}`;
    } else if (value < 0) {
        return `${value.toFixed(2)}${unit}`;
    }
    return `0.00${unit}`;
}

/**
 * 取得數值的增減顏色類別
 * @param {number} value - 數值
 * @returns {string} CSS 類別名稱
 */
function getValueColorClass(value) {
    if (value > 0) return "val-positive";
    if (value < 0) return "val-negative";
    return "val-neutral";
}

/**
 * 取得數值的卡片邊界發光類別
 * @param {number} value - 數值
 * @returns {string} CSS 類別名稱
 */
function getCardGlowClass(value) {
    if (value > 0) return "card-buy";
    if (value < 0) return "card-sell";
    return "card-neutral";
}

let allHistoryData = [];
let todayData = null;

/**
 * 載入並渲染盤後籌碼 JSON 數據 (支援歷史數據與多日累計切換)
 */
async function loadChipsData() {
    try {
        // 1. 先嘗試載入今日最新數據
        const todayResponse = await fetch("data/daily_chips.json");
        if (todayResponse.ok) {
            todayData = await todayResponse.json();
        }
        
        // 2. 嘗試載入歷史累計數據
        const historyResponse = await fetch("data/daily_chips_history.json");
        if (historyResponse.ok) {
            const historyJson = await historyResponse.json();
            allHistoryData = historyJson.history || [];
        }
        
        // 3. 初始化並渲染日期下拉選單
        populateDateSelector();
        
        // 4. 預設渲染今日數據，若今日無資料則渲染歷史數據中的最後一天
        if (todayData) {
            renderDashboard(todayData);
        } else if (allHistoryData.length > 0) {
            const latestHistory = allHistoryData[allHistoryData.length - 1];
            renderDashboardFromHistory(latestHistory);
        } else {
            showErrorState();
        }
    } catch (error) {
        console.error("載入台股籌碼數據失敗:", error);
        showErrorState();
    }
}

/**
 * 建立並監聽日期下拉選單
 */
function populateDateSelector() {
    const selector = document.getElementById("date-select");
    if (!selector) return;
    
    selector.innerHTML = "";
    
    // 如果有今日最新資料，優先加入選項
    if (todayData) {
        const opt = document.createElement("option");
        opt.value = "today";
        opt.textContent = `${todayData.date} (今日最新)`;
        selector.appendChild(opt);
    }
    
    const todayDateStr = todayData ? todayData.date : "";
    
    // 將歷史資料以日期從新到舊排序加入下拉選單 (避免重複今日日期)
    for (let i = allHistoryData.length - 1; i >= 0; i--) {
        const entry = allHistoryData[i];
        if (entry.date === todayDateStr) continue;
        
        const opt = document.createElement("option");
        opt.value = entry.date;
        opt.textContent = entry.date;
        selector.appendChild(opt);
    }
    
    // 監聽日期切換事件
    selector.addEventListener("change", (e) => {
        const selectedValue = e.target.value;
        if (selectedValue === "today") {
            renderDashboard(todayData);
        } else {
            const foundEntry = allHistoryData.find(item => item.date === selectedValue);
            if (foundEntry) {
                renderDashboardFromHistory(foundEntry);
            }
        }
    });
}

/**
 * 將歷史條目轉換映射成 Render 格式進行儀表板渲染
 * @param {Object} entry - 歷史資料條目
 */
function renderDashboardFromHistory(entry) {
    const mappedData = {
        date: entry.date,
        market_summary: {
            combined: entry.combined_summary,
            tse: entry.tse_summary,
            tpex: entry.tpex_summary
        },
        gov_banks: entry.gov_banks,
        margin_trading: entry.margin_trading,
        trading_volume: entry.trading_volume,
        tsmc_chips: entry.tsmc_chips,
        rankings: {
            foreign_buy: [],
            foreign_sell: [],
            trust_buy: [],
            trust_sell: []
        }
    };
    
    renderDashboard(mappedData);
    
    // 歷史數據不含個股前十名排行，提示使用者點選下載 CSV 檢視
    const rankingTableIds = [
        "table-foreign-buy-body", "table-foreign-sell-body",
        "table-trust-buy-body", "table-trust-sell-body"
    ];
    rankingTableIds.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.innerHTML = `<tr><td colspan="3" class="text-center" style="color: var(--text-muted); padding: 15px;">歷史個股排行，請點選右上角下載每日 CSV 數據查看</td></tr>`;
        }
    });
}

/**
 * 將資料渲染至金融面板
 * @param {Object} data - 籌碼資料物件
 */
function renderDashboard(data) {
    // 1. 更新資料日期與更新時間
    const dataDateElement = document.getElementById("data-date");
    if (dataDateElement) {
        dataDateElement.textContent = data.date || "無資料";
    }

    // 2. 渲染三大法人買賣超金額 (使用 Combined tse + otc 合計數據以呈現大盤全貌)
    const summary = data.market_summary.combined;
    
    // 外資卡片
    updateStatCard("card-foreign", "val-foreign", summary.foreign);
    // 投信卡片
    updateStatCard("card-trust", "val-trust", summary.trust);
    // 自營商卡片
    updateStatCard("card-dealer", "val-dealer", summary.dealer);
    
    // 八大官股卡片 (注意：八大官股的統計日期可能略有不同)
    const govData = data.gov_banks;
    updateStatCard("card-gov", "val-gov", govData.net_buy);
    
    // 為八大官股卡片下方補充小字標記數據來源日期
    const govTitle = document.querySelector("#card-gov .stat-title");
    if (govTitle && govData.date) {
        govTitle.innerHTML = `八大官股行庫 <span style="font-size:10px; opacity:0.7;">(${govData.date})</span>`;
    }

    // 3. 大盤信用交易與成交值
    const margin = data.margin_trading;
    const volume = data.trading_volume;
    
    // 融資餘額增減
    const valMarginBuy = document.getElementById("val-margin-buy");
    if (valMarginBuy) {
        valMarginBuy.textContent = formatNetValue(margin.margin_balance_change);
        valMarginBuy.className = `margin-value ${getValueColorClass(margin.margin_balance_change)}`;
    }
    
    // 融券餘額增減 (融券以張為單位)
    const valMarginSell = document.getElementById("val-margin-sell");
    if (valMarginSell) {
        const changeSheets = margin.short_balance_change;
        const formattedSheets = changeSheets > 0 ? `+${changeSheets.toLocaleString()} 張` : `${changeSheets.toLocaleString()} 張`;
        valMarginSell.textContent = formattedSheets;
        valMarginSell.className = `margin-value ${getValueColorClass(changeSheets)}`;
    }
    
    // 大盤成交金額
    const valTotalVolume = document.getElementById("val-total-volume");
    if (valTotalVolume) {
        valTotalVolume.textContent = `${volume.tse_volume.toFixed(2)} 億`;
        valTotalVolume.className = "margin-value val-neutral";
    }

    // 3.5 渲染台積電 (2330) 三大法人買賣超 (張數)
    const tsmc = data.tsmc_chips || { foreign: 0, trust: 0, dealer: 0, total: 0 };
    updateTsmcBox("tsmc-box-foreign", "val-tsmc-foreign", tsmc.foreign);
    updateTsmcBox("tsmc-box-trust", "val-tsmc-trust", tsmc.trust);
    updateTsmcBox("tsmc-box-dealer", "val-tsmc-dealer", tsmc.dealer);
    updateTsmcBox("tsmc-box-total", "val-tsmc-total", tsmc.total);

    // 4. 渲染個股排行
    renderRankingsTable("table-foreign-buy-body", data.rankings.foreign_buy, "buy");
    renderRankingsTable("table-foreign-sell-body", data.rankings.foreign_sell, "sell");
    renderRankingsTable("table-trust-buy-body", data.rankings.trust_buy, "buy");
    renderRankingsTable("table-trust-sell-body", data.rankings.trust_sell, "sell");
}

/**
 * 更新台積電買賣超個股統計 Box
 * @param {string} boxId - 區塊元素 ID
 * @param {string} valueId - 數值元素 ID
 * @param {number} value - 張數
 */
function updateTsmcBox(boxId, valueId, value) {
    const boxEl = document.getElementById(boxId);
    const valueEl = document.getElementById(valueId);
    
    if (valueEl) {
        const formatted = value > 0 ? `+${value.toLocaleString()} 張` : `${value.toLocaleString()} 張`;
        valueEl.textContent = formatted;
        valueEl.className = `tsmc-value ${getValueColorClass(value)}`;
    }
    
    if (boxEl) {
        boxEl.style.borderColor = value > 0 ? 'rgba(239, 68, 68, 0.3)' : (value < 0 ? 'rgba(16, 185, 129, 0.3)' : 'var(--border-color)');
        boxEl.style.background = value > 0 ? 'rgba(239, 68, 68, 0.02)' : (value < 0 ? 'rgba(16, 185, 129, 0.02)' : 'rgba(255, 255, 255, 0.02)');
    }
}

/**
 * 更新單個買賣超統計卡片內容與樣式
 * @param {string} cardId - 卡片元素 ID
 * @param {string} valueId - 數值元素 ID
 * @param {number} value - 金額 (億元)
 */
function updateStatCard(cardId, valueId, value) {
    const cardEl = document.getElementById(cardId);
    const valueEl = document.getElementById(valueId);
    
    if (valueEl) {
        valueEl.textContent = formatNetValue(value);
        valueEl.className = `stat-value ${getValueColorClass(value)}`;
    }
    
    if (cardEl) {
        // 清理原先的發光類別，重新注入
        cardEl.classList.remove("card-buy", "card-sell", "card-neutral");
        cardEl.classList.add(getCardGlowClass(value));
    }
}

/**
 * 渲染排行表格
 * @param {string} tbodyId - 表格 Body 元素 ID
 * @param {Array} list - 個股數據陣列
 * @param {string} type - 'buy' (買超) 或 'sell' (賣超)
 */
function renderRankingsTable(tbodyId, list, type) {
    const tbody = document.getElementById(tbodyId);
    if (!tbody) return;
    
    tbody.innerHTML = "";
    
    if (!list || list.length === 0) {
        tbody.innerHTML = `<tr><td colspan="3" class="text-center" style="color: var(--text-muted);">本日無相關排行資料</td></tr>`;
        return;
    }
    
    list.forEach(item => {
        const tr = document.createElement("tr");
        
        // 排名 badge 的樣式
        let rankBadgeClass = "rank-badge";
        if (item.rank === 1) rankBadgeClass += " rank-badge-1";
        else if (item.rank === 2) rankBadgeClass += " rank-badge-2";
        else if (item.rank === 3) rankBadgeClass += " rank-badge-3";
        
        // 買超與賣超數字顯示顏色
        const valColorClass = type === "buy" ? "val-positive" : "val-negative";
        
        tr.innerHTML = `
            <td><span class="${rankBadgeClass}">${item.rank}</span></td>
            <td>
                <span class="stock-code">${item.code}</span>
                <a href="https://tw.stock.yahoo.com/quote/${item.code}" target="_blank" class="stock-link">${item.name}</a>
            </td>
            <td class="text-right ${valColorClass}">${item.volume.toLocaleString()} 張</td>
        `;
        
        tbody.appendChild(tr);
    });
}

/**
 * 當加載失敗或無今日交易數據時的備用 UI 狀態
 */
function showErrorState() {
    const dataDateElement = document.getElementById("data-date");
    if (dataDateElement) {
        dataDateElement.innerHTML = `<span style="color: var(--text-muted);">無交易日數據 (週末/非交易日)</span>`;
    }
    
    // 將卡片與信用交易欄位置為預設值
    const placeholders = [
        "val-foreign", "val-trust", "val-dealer", "val-gov",
        "val-margin-buy", "val-margin-sell", "val-total-volume",
        "val-tsmc-foreign", "val-tsmc-trust", "val-tsmc-dealer", "val-tsmc-total"
    ];
    
    placeholders.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.textContent = (id.includes("sell") || id.includes("tsmc")) ? "0 張" : "0.0 億";
            el.className = id.includes("volume") ? "margin-value val-neutral" : (id.includes("tsmc") ? "tsmc-value val-neutral" : "stat-value val-neutral");
        }
    });

    const tables = [
        "table-foreign-buy-body", "table-foreign-sell-body",
        "table-trust-buy-body", "table-trust-sell-body"
    ];
    
    tables.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.innerHTML = `<tr><td colspan="3" class="text-center" style="color: var(--text-muted);">暫無今日籌碼數據</td></tr>`;
        }
    });
}
