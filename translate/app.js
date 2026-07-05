/* ==========================================================================
   估購翻譯 - 互動與 MyMemory API 翻譯邏輯 (app.js)
   ========================================================================== */

document.addEventListener("DOMContentLoaded", () => {
    // 元素綁定
    const sourceText = document.getElementById("source-text");
    const targetText = document.getElementById("target-text");
    const outputPlaceholder = document.getElementById("output-placeholder");
    const translateBtn = document.getElementById("translate-btn");
    const swapLangBtn = document.getElementById("swap-lang-btn");
    
    const sourceLangLabel = document.getElementById("source-lang-label");
    const targetLangLabel = document.getElementById("target-lang-label");
    const charCounter = document.getElementById("char-counter");
    const translationStatus = document.getElementById("translation-status");
    
    const clearBtn = document.getElementById("clear-btn");
    const copyBtn = document.getElementById("copy-btn");
    const ttsSourceBtn = document.getElementById("tts-source-btn");
    const ttsTargetBtn = document.getElementById("tts-target-btn");
    
    const playPhraseBtns = document.querySelectorAll(".play-phrase-btn");

    // 翻譯方向狀態：true = 中翻義, false = 義翻中
    let isChineseToItalian = true;

    // 1. 字數計數器與占位符處理
    sourceText.addEventListener("input", () => {
        const len = sourceText.value.length;
        charCounter.textContent = `${len} / 1000`;
        if (len > 1000) {
            sourceText.value = sourceText.value.substring(0, 1000);
            charCounter.textContent = "1000 / 1000";
        }
    });

    // 2. 切換語言方向
    swapLangBtn.addEventListener("click", () => {
        isChineseToItalian = !isChineseToItalian;
        
        // 切換標籤文字
        if (isChineseToItalian) {
            sourceLangLabel.textContent = "繁體中文";
            targetLangLabel.textContent = "義大利文 (Italiano)";
            sourceText.placeholder = "請輸入要翻譯的文字...";
        } else {
            sourceLangLabel.textContent = "義大利文 (Italiano)";
            targetLangLabel.textContent = "繁體中文";
            sourceText.placeholder = "Inserisci il testo da tradurre...";
        }

        // 交換輸入框與輸出框的內容
        const tempText = sourceText.value;
        sourceText.value = targetText.value;
        targetText.value = tempText;

        // 觸發輸入框的 input 事件以更新字數
        sourceText.dispatchEvent(new Event("input"));
        updatePlaceholderVisibility();
    });

    // 3. 呼叫 MyMemory API 進行翻譯
    async function performTranslation() {
        const query = sourceText.value.trim();
        if (!query) {
            targetText.value = "";
            updatePlaceholderVisibility();
            return;
        }

        translationStatus.textContent = "翻譯中...";
        translateBtn.disabled = true;
        translateBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> 正在翻譯...`;

        // 語系代碼定義
        const sourceLang = isChineseToItalian ? "zh-TW" : "it-IT";
        const targetLang = isChineseToItalian ? "it-IT" : "zh-TW";
        const langpair = `${sourceLang}|${targetLang}`;

        // MyMemory 官方免金鑰 GET 接口
        const apiUrl = `https://api.mymemory.translated.net/get?q=${encodeURIComponent(query)}&langpair=${langpair}`;

        try {
            const response = await fetch(apiUrl);
            if (!response.ok) {
                throw new Error("網路連線錯誤");
            }
            const data = await response.json();
            
            if (data.responseData && data.responseData.translatedText) {
                // MyMemory 有時會返回帶有 HTML 實體編碼的文字，進行解碼
                const decodedText = decodeHTMLEntities(data.responseData.translatedText);
                targetText.value = decodedText;
                translationStatus.textContent = "翻譯成功";
            } else {
                throw new Error("無法解析翻譯結果");
            }
        } catch (error) {
            console.error("翻譯失敗:", error);
            targetText.value = "翻譯出錯，請稍後重試。";
            translationStatus.textContent = "翻譯失敗";
        } finally {
            translateBtn.disabled = false;
            translateBtn.innerHTML = `<i class="fa-solid fa-language"></i> 立即翻譯`;
            updatePlaceholderVisibility();
        }
    }

    translateBtn.addEventListener("click", performTranslation);

    // 4. 清除與複製按鈕
    clearBtn.addEventListener("click", () => {
        sourceText.value = "";
        targetText.value = "";
        charCounter.textContent = "0 / 1000";
        translationStatus.textContent = "Ready";
        updatePlaceholderVisibility();
    });

    copyBtn.addEventListener("click", () => {
        const text = targetText.value;
        if (!text) return;

        navigator.clipboard.writeText(text).then(() => {
            const originalIcon = copyBtn.innerHTML;
            copyBtn.innerHTML = `<i class="fa-solid fa-check" style="color: var(--color-sell);"></i>`;
            translationStatus.textContent = "已複製到剪貼簿";
            setTimeout(() => {
                copyBtn.innerHTML = originalIcon;
                translationStatus.textContent = "Ready";
            }, 1500);
        }).catch(err => {
            console.error("複製失敗:", err);
        });
    });

    // 5. 瀏覽器原生語音朗讀 (Text-to-Speech)
    function speakText(text, lang) {
        if (!text) return;
        
        // 取消目前正在播放的語音
        window.speechSynthesis.cancel();
        
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = lang;
        
        // 尋找對應語系的系統語音
        const voices = window.speechSynthesis.getVoices();
        const matchedVoice = voices.find(voice => voice.lang.startsWith(lang));
        if (matchedVoice) {
            utterance.voice = matchedVoice;
        }

        window.speechSynthesis.speak(utterance);
    }

    ttsSourceBtn.addEventListener("click", () => {
        const lang = isChineseToItalian ? "zh-TW" : "it-IT";
        speakText(sourceText.value, lang);
    });

    ttsTargetBtn.addEventListener("click", () => {
        const lang = isChineseToItalian ? "it-IT" : "zh-TW";
        speakText(targetText.value, lang);
    });

    // 常用對話點擊播放語音
    playPhraseBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            const text = btn.getAttribute("data-text");
            speakText(text, "it-IT");
        });
    });

    // 6. 輔助函數：更新佔位符顯示
    function updatePlaceholderVisibility() {
        if (targetText.value) {
            outputPlaceholder.style.opacity = "0";
        } else {
            outputPlaceholder.style.opacity = "1";
        }
    }

    // 7. 輔助函數：解碼 HTML Entities (例如 &quot; 轉為 ")
    function decodeHTMLEntities(text) {
        const textArea = document.createElement("textarea");
        textArea.innerHTML = text;
        return textArea.value;
    }

    // 確保語音資源加載
    window.speechSynthesis.onvoiceschanged = () => {};
});
