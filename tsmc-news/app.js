/* ==========================================================================
   台積電新聞與股價即時追蹤器 - 互動與資料加載 (app.js)
   ========================================================================== */

let countdownValue = 60;
let timerId = null;
let globalNewsData = [];

document.addEventListener("DOMContentLoaded", () => {
    // 1. 載入即時股價與新聞
    loadDashboardData();

    // 2. 啟動倒數計時器
    startCountdown();
});

/**
 * 啟動倒數計時器
 */
function startCountdown() {
    const timerEl = document.getElementById("countdown-timer");
    
    if (timerId) {
        clearInterval(timerId);
    }
    
    timerId = setInterval(() => {
        countdownValue--;
        if (timerEl) {
            timerEl.textContent = `${countdownValue}s`;
        }
        
        if (countdownValue <= 0) {
            countdownValue = 60;
            loadDashboardData();
        }
    }, 1000);
}

/**
 * 載入並解析新聞與股價 JSON 數據
 */
async function loadDashboardData() {
    const dataUrl = "data/tsmc_news.json";
    
    try {
        const response = await fetch(dataUrl);
        if (!response.ok) {
            throw new Error(`HTTP 錯誤! 狀態碼: ${response.status}`);
        }
        const data = await response.json();
        
        globalNewsData = data.news || [];
        
        // 渲染儀表板
        renderPrices(data.stock_prices);
        renderNewsFeed(globalNewsData);
        
        // 更新更新時間
        const lastUpdatedEl = document.getElementById("last-updated");
        if (lastUpdatedEl) {
            lastUpdatedEl.textContent = data.last_updated || "無資料";
        }
    } catch (error) {
        console.error("加載 TSMC 即時新聞數據失敗:", error);
        showErrorState();
    }
}

// Subscription helper functions removed

/**
 * 渲染台美股價與漲跌 (符合兩地股市顏色規範)
 * @param {Object} prices - 股價數據物件
 */
function renderPrices(prices) {
    // 1. 渲染台股 (2330.TW) - 台灣色彩習慣：紅漲綠跌
    const tw = prices.tw_2330;
    const priceTwEl = document.getElementById("price-tw");
    const changeTwEl = document.getElementById("change-tw");
    
    if (priceTwEl && changeTwEl) {
        priceTwEl.textContent = tw.price > 0 ? tw.price.toFixed(1) : "未開盤";
        
        if (tw.price > 0) {
            const prefix = tw.change > 0 ? "▲" : (tw.change < 0 ? "▼" : "");
            changeTwEl.textContent = `${prefix} ${Math.abs(tw.change).toFixed(1)} (${tw.change_percent.toFixed(2)}%)`;
            
            // 套用台灣色彩
            changeTwEl.className = "ticker-change";
            priceTwEl.className = "ticker-price";
            if (tw.change > 0) {
                changeTwEl.classList.add("price-up");
                priceTwEl.classList.add("price-up");
            } else if (tw.change < 0) {
                changeTwEl.classList.add("price-down");
                priceTwEl.classList.add("price-down");
            }
        } else {
            changeTwEl.textContent = "--";
            changeTwEl.className = "ticker-change";
        }
    }

    // 2. 渲染美股 (TSM) - 美股色彩習慣：綠漲紅跌
    const us = prices.us_tsm;
    const priceUsEl = document.getElementById("price-us");
    const changeUsEl = document.getElementById("change-us");
    
    if (priceUsEl && changeUsEl) {
        priceUsEl.textContent = us.price > 0 ? `$${us.price.toFixed(2)}` : "未開盤";
        
        if (us.price > 0) {
            const prefix = us.change > 0 ? "+" : "";
            changeUsEl.textContent = `${prefix}${us.change.toFixed(2)} (${prefix}${us.change_percent.toFixed(2)}%)`;
            
            // 套用美股色彩
            changeUsEl.className = "ticker-change";
            priceUsEl.className = "ticker-price";
            if (us.change > 0) {
                changeUsEl.classList.add("price-us-up");
                priceUsEl.classList.add("price-us-up");
            } else if (us.change < 0) {
                changeUsEl.classList.add("price-us-down");
                priceUsEl.classList.add("price-us-down");
            }
        } else {
            changeUsEl.textContent = "--";
            changeUsEl.className = "ticker-change";
        }
    }
}

/**
 * 渲染新聞串流列表 (純時間順序)
 * @param {Array} newsList - 所有新聞數據
 */
function renderNewsFeed(newsList) {
    const listEl = document.getElementById("news-list");
    if (!listEl) return;
    
    listEl.innerHTML = "";
    
    if (newsList.length === 0) {
        listEl.innerHTML = `
            <div class="news-error">
                <i class="fa-solid fa-folder-open loader-icon" style="opacity: 0.5;"></i>
                <span>目前無新聞資料</span>
            </div>
        `;
        return;
    }
    
    newsList.forEach(item => {
        const card = document.createElement("div");
        card.className = "news-card";
        
        card.innerHTML = `
            <div class="news-meta">
                <div class="meta-left">
                    <span class="news-source">鉅亨網</span>
                    <span class="news-time">${item.publish_time}</span>
                </div>
            </div>
            
            <h3 class="news-title">
                <a href="${item.url}" target="_blank" class="news-link">${item.title}</a>
            </h3>
            
            <!-- 可展開大綱區 -->
            <div class="news-summary-wrapper" id="summary-${item.news_id}">
                <p class="news-summary">${item.summary || "無詳細摘要"}</p>
            </div>
            
            <div class="news-footer">
                <div class="news-tags">
                    ${item.keywords.slice(0, 3).map(tag => `<span class="tag">#${tag}</span>`).join('')}
                </div>
                <button class="expand-btn" data-id="${item.news_id}">
                    <span>展開大綱</span>
                    <i class="fa-solid fa-chevron-down"></i>
                </button>
            </div>
        `;
        
        listEl.appendChild(card);
    });
    
    initExpandButtons();
}

/**
 * 初始化展開按鈕事件
 */
function initExpandButtons() {
    const expandButtons = document.querySelectorAll(".expand-btn");
    
    expandButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            const newsId = btn.getAttribute("data-id");
            const wrapper = document.getElementById(`summary-${newsId}`);
            const span = btn.querySelector("span");
            const icon = btn.querySelector("i");
            
            if (wrapper) {
                const isExpanded = wrapper.classList.toggle("expanded");
                
                if (isExpanded) {
                    span.textContent = "收合大綱";
                    icon.className = "fa-solid fa-chevron-up";
                } else {
                    span.textContent = "展開大綱";
                    icon.className = "fa-solid fa-chevron-down";
                }
            }
        });
    });
}

// Subscription form handlers removed

/**
 * 載入出錯時的備份顯示狀態
 */
function showErrorState() {
    const listEl = document.getElementById("news-list");
    if (listEl) {
        listEl.innerHTML = `
            <div class="news-error">
                <i class="fa-solid fa-triangle-exclamation loader-icon" style="color: var(--tw-up);"></i>
                <span>加載即時新聞失敗。請確保啟動腳本 (start_dashboard.py) 運作正常。</span>
            </div>
        `;
    }
}
