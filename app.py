import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import datetime
import time
import random
import re
import json
import os

# ==========================================
# 0. 系統設定與 CSS 優化 (System Config)
# ==========================================
st.set_page_config(
    page_title="ISO 45001 智慧法規合規管理戰情室 V2.3",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定義 CSS
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stButton>button { width: 100%; border-radius: 5px; font-weight: bold; }
    .status-card {
        padding: 15px; border-radius: 10px; border: 1px solid #ddd;
        margin-bottom: 10px; background-color: white;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
    }
    .step-header {
        background-color: #e3f2fd; padding: 10px; border-radius: 5px;
        margin: 10px 0; border-left: 5px solid #2196f3;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 1. 資料持久化與 Session State 初始化 
# ==========================================
DATA_FILE = "audit_records.json"

def load_records():
    """從本地 JSON 檔案讀取查核紀錄"""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_records(records):
    """將查核紀錄儲存至本地 JSON 檔案"""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=4)

def init_session_state():
    # 用於在 Tab 1 點擊分析後，將標題帶入 Tab 2
    if 'analysis_input_title' not in st.session_state:
        st.session_state['analysis_input_title'] = ""
    
    # [V2.2 Strict State Machine for Tab 2]
    # 1. 記錄步驟一 (適用性判斷) 是否通過
    if 'step1_confirmed' not in st.session_state:
        st.session_state.step1_confirmed = False
    
    # 2. 記錄步驟二 (詳細分析) 的結果 DataFrame
    if 'analysis_df' not in st.session_state:
        st.session_state.analysis_df = None

    # 3. 記錄步驟二輸入的條文內容 (防止重整後消失)
    if 'law_content_buffer' not in st.session_state:
        st.session_state.law_content_buffer = ""
    
    # 儲存抓取到的新聞列表
    if 'regulatory_news' not in st.session_state:
        st.session_state['regulatory_news'] = []
    
    # 儲存查核案件 (包含待簽核與歷史紀錄) - [加入持久化讀取邏輯]
    if 'audit_records' not in st.session_state:
        st.session_state.audit_records = load_records()

init_session_state()

# ==========================================
# 2. 爬蟲與數據模擬核心 (Scraping Core)
# ==========================================

def get_mock_data_by_source(source_name):
    """根據來源提供特定的模擬數據 (Failover Mock Data) - [擴充逼真假資料]"""
    today = datetime.date.today().strftime("%Y-%m-%d")
    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    last_week = (datetime.date.today() - datetime.timedelta(days=7)).strftime("%Y-%m-%d")
    
    if "勞動部職安署" in source_name:
        return [
            {"title": "修正「職業安全衛生設施規則」部分條文，強化機械設備防護", "date": today, "source": "OSHA"},
            {"title": "公告：起重升降機具安全規則修正草案總說明", "date": yesterday, "source": "OSHA"},
            {"title": "發布「職場夜間工作安全衛生指引」", "date": yesterday, "source": "OSHA"},
            {"title": "預告修正「危險性工作場所審查及檢查辦法」", "date": last_week, "source": "OSHA"},
        ]
    elif "行政院公報" in source_name:
        return [
            {"title": "預告訂定「碳費徵收費率」草案", "date": today, "source": "Gazette"},
            {"title": "修正「工廠管理輔導法」第28條解釋令", "date": yesterday, "source": "Gazette"},
            {"title": "發布「事業單位執行預防勞工過勞指引」新修訂版", "date": last_week, "source": "Gazette"},
        ]
    elif "環境部" in source_name:
        return [
            {"title": "修正「固定污染源空氣污染防制費收費費率」", "date": today, "source": "EPA"},
            {"title": "廢棄物清理法部分條文修正草案", "date": yesterday, "source": "EPA"},
            {"title": "公告「溫室氣體排放量盤查登錄管理辦法」", "date": last_week, "source": "EPA"},
        ]
    elif "全國法規資料庫" in source_name:
        return [
            {"title": "修正「勞工健康保護規則」", "date": today, "source": "MOJ"},
            {"title": "增訂「危險性機械及設備安全檢查規則」部分條文", "date": yesterday, "source": "MOJ"},
            {"title": "修正「勞工職業災害保險及保護法」", "date": last_week, "source": "MOJ"},
        ]
    return []

def fetch_regulatory_news(sources):
    """模擬串接政府開放資料 API 或 RSS Feed (改寫 JSON 讀取邏輯)"""
    results = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    # 模擬政府 Open Data API 端點 (實務上會替換為真實的 JSON API 網址)
    api_endpoints = {
        "勞動部職安署 (OSHA)": "https://data.gov.tw/api/osha/v1/news.json",
        "行政院公報資訊網": "https://data.gov.tw/api/gazette/v1/latest.json",
        "環境部主管法規查詢系統": "https://data.gov.tw/api/epa/v1/law.json",
        "全國法規資料庫": "https://data.gov.tw/api/moj/v1/law.json"
    }

    for source in sources:
        url = api_endpoints.get(source, "https://example.com/api")
        try:
            # 模擬請求 JSON API，設定 timeout 防止卡死
            response = requests.get(url, headers=headers, timeout=5)
            response.raise_for_status()
            
            # [改寫] 改為 JSON 讀取邏輯
            data = response.json()
            found_items = []
            
            # 假設標準 Open Data 回傳格式包含 "records" 陣列
            for item in data.get("records", [])[:3]:
                found_items.append({
                    "title": item.get("title", ""),
                    "date": item.get("date", datetime.date.today().strftime("%Y-%m-%d")),
                    "source": source
                })
            
            if not found_items:
                raise ValueError("JSON API 中找不到預期資料")
                
            results.extend(found_items)
            
        except Exception:
            # Fallback 備援機制：觸發並載入擴充後的假資料
            mock_items = get_mock_data_by_source(source)
            for item in mock_items:
                item['title'] = f"[演示] {item['title']}"
            results.extend(mock_items)
            
    return results

# ==========================================
# 3. AI 模擬邏輯 (AI Simulation)
# ==========================================

def ai_applicability_check(text, equipment_list):
    """第一階段：適用性初判"""
    text_lower = text.lower()
    relevant_keywords = ['機械', '安全', '衛生', '勞工', '環保', '碳費', '起重', '健康', '檢查', '危險']
    irrelevant_keywords = ['食品', '交通', '銀行', '教育', '觀光', '農委會']
    
    for eq in equipment_list:
        if eq in text:
            return True, f"✅ 與廠內設備「{eq}」高度相關。"
            
    if any(k in text for k in irrelevant_keywords):
        return False, "❌ 屬於非相關產業 (如食品/金融/交通)。"
    
    if any(k in text for k in relevant_keywords):
        return True, "✅ 包含職安衛/環保關鍵詞，建議進一步評估。"
        
    return False, "無明確關鍵字，建議人工確認。"

def ai_generate_detailed_table(law_content):
    """第二階段：生成逐條分析表 (V2.3 Regex修復與關鍵字擴充版)"""
    lines = law_content.split('\n')
    data = []
    
    current_article = "第X條" # 記錄當前遍歷到的法規條次

    # [擴充] AI 適用性判讀高風險關鍵字
    high_keywords = ['應', '不得', '罰鍰', '霸凌', '不法侵害', '健康', '體格檢查', '母性', '噪音', '粉塵', '人因', '墜落', '感電', '防護', '承攬', '危害', '風險', '通風', '局排', '溶劑', '許可', '檢查', '申訴', '職災', '職業病', '安全', '衛生', '防護具']

    for line in lines:
        line = line.strip()
        if len(line) < 2: continue # 忽略空行
        
        # [修復 Regex 1] 處理章節 (如: 第 一 章 總則)，作為獨立標題列
        match_chapter = re.match(r'^(第\s*[一二三四五六七八九十百千\d]+\s*章)\s*(.*)', line)
        if match_chapter:
            chapter_num = match_chapter.group(1).replace(" ", "")
            chapter_title = match_chapter.group(2).strip()
            data.append({
                "條文/項次": chapter_num,
                "條文內容摘要": f"【章節標題】{chapter_title}" if chapter_title else "【章節標題】",
                "適用性": "-"
            })
            continue

        # [修復 Regex 2] 支援「第 X 條」、「第 X 條之 X」、「第 X-X 條」
        match_article = re.match(r'^(第\s*[一二三四五六七八九十百千\d]+(?:\s*之\s*\d+|-\d+)?\s*條)\s*(.*)', line)
        
        if match_article:
            # 抓到新條文，更新當前條次
            current_article = match_article.group(1).replace(" ", "")
            content = match_article.group(2).strip()
            
            if not content:
                # 若這行只有「第 6 條」而沒有內容，跳過此迴圈，等下一行處理內容
                continue 
            
            clause = f"{current_article}序文"
        else:
            # 如果不是新條文，判斷是否為「款」或「項」 (一、二、三...)
            match_item = re.match(r'^([一二三四五六七八九十]+、)\s*(.*)', line)
            if match_item:
                clause_num = match_item.group(1).replace("、", "")
                content = match_item.group(2).strip()
                clause = f"{current_article}第{clause_num}款"
            else:
                # 一般內文
                clause = f"{current_article}內容"
                content = line
                
        if not content:
            continue

        # [擴充邏輯] 只要包含清單中任一關鍵字即為高
        applicability = "高" if any(k in content for k in high_keywords) else "低"
        
        data.append({
            "條文/項次": clause,
            "條文內容摘要": content[:30] + "..." if len(content) > 30 else content,
            "適用性": applicability
        })
        
    if not data:
        data = [{"條文/項次": "無", "條文內容摘要": "無可解析之內容", "適用性": "-"}]

    return pd.DataFrame(data)

# ==========================================
# 4. UI 介面佈局 (Streamlit Layout)
# ==========================================

with st.sidebar:
    st.title("用戶中心")
    st.markdown("<h1 style='text-align: center; font-size: 75px; margin-top: -10px; margin-bottom: 10px;'>⛑️</h1>", unsafe_allow_html=True)
    
    user_role = st.selectbox("切換身份", ["職安室成員", "職安室主管"])
    st.info(f"目前登入：**{user_role}**")
    st.divider()
    st.caption("ISO 45001 War Room V2.3")

st.title("🛡️ ISO 45001 智慧法規合規管理戰情室 V2.3")

# Tabs
tab1, tab2, tab3 = st.tabs(["📡 法規監控雷達", "🧠 適用性智慧判讀", "📝 合規簽核紀錄"])

# ------------------------------------------------------------------
# 分頁 1: 法規監控雷達
# ------------------------------------------------------------------
with tab1:
    st.subheader("📡 全域法規源監測 (Global Monitor)")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        sources = st.multiselect(
            "選擇監測來源 (支援多選)：",
            ["勞動部職安署 (OSHA)", "行政院公報資訊網", "環境部主管法規查詢系統", "全國法規資料庫"],
            default=["勞動部職安署 (OSHA)", "環境部主管法規查詢系統"]
        )
    with col2:
        st.write("") 
        st.write("") 
        start_scraping = st.button("🚀 啟動智能爬蟲 (V2.3)", use_container_width=True)

    if start_scraping:
        with st.spinner("正在連線外部資料庫 (Timeout: 5s)..."):
            time.sleep(1)
            news_data = fetch_regulatory_news(sources)
            st.session_state['regulatory_news'] = news_data
            st.success(f"掃描完成！共發現 {len(news_data)} 條相關動態。")

    if st.session_state['regulatory_news']:
        st.markdown("### 📋 最新監測結果")
        for i, news in enumerate(st.session_state['regulatory_news']):
            with st.container():
                c1, c2, c3, c4 = st.columns([1, 1.5, 4, 1.5])
                with c1: st.caption(news['source'])
                with c2: st.caption(f"📅 {news['date']}")
                with c3: st.markdown(f"**{news['title']}**")
                with c4:
                    if st.button("🔍 分析此條文", key=f"btn_src_{i}"):
                        st.session_state['analysis_input_title'] = news['title']
                        st.session_state.step1_confirmed = False # 切換條文時重置狀態
                        st.session_state.analysis_df = None      # 切換條文時重置狀態
                        # [優化 UX] 提示文字更新
                        st.toast(f"已將「{news['title']}」帶入分析區，請切換至【適用性智慧判讀】分頁", icon="✅")
                st.divider()

# ------------------------------------------------------------------
# 分頁 2: 適用性智慧判讀 (State-Driven Logic)
# ------------------------------------------------------------------
with tab2:
    st.subheader("🧠 兩階段適用性判讀 (State-Driven Logic)")
    
    st.markdown('<div class="step-header">步驟一：法規適用性評估 (Applicability Check)</div>', unsafe_allow_html=True)
    
    st.info("🏭 當前廠區設定：工具機製造業 (Taichung Plant)")
    
    col_a_input, col_a_btn = st.columns([3, 1])
    
    with col_a_input:
        # [擴充] 廠區設備更新
        equipment_selected = st.multiselect(
            "關聯廠內設備/製程：",
            ['CNC機台', '堆高機', '高壓氣體', '天車', '熔解爐', '化學品', '有機溶劑', '研磨輪', '高空工作車', '圓盤鋸', '退火爐'],
            default=['CNC機台', '化學品']
        )
        # [擴充] 新增議題類別
        issue_selected = st.multiselect(
            "涉及危害/議題類別：",
            ['噪音', '粉塵', '人因工程', '不法侵害(霸凌)', '化學性危害', '健康檢查', '母性保護'],
            default=['不法侵害(霸凌)']
        )
        
        input_title = st.text_input(
            "法規名稱 / 議題概述：", 
            value=st.session_state['analysis_input_title'],
            placeholder="請輸入法規名稱...",
            key="input_title_key"
        )
        
    with col_a_btn:
        st.write("")
        st.write("")
        if st.button("🤖 執行適用性 AI 初判", type="primary"):
            if input_title:
                is_app, reason = ai_applicability_check(input_title, equipment_selected)
                if is_app:
                    st.success(reason)
                    st.session_state.step1_confirmed = True  
                    st.session_state.analysis_df = None      
                else:
                    st.error(reason)
                    st.session_state.step1_confirmed = False 
                    st.session_state.analysis_df = None
            else:
                st.warning("請輸入法規名稱")

    if st.session_state.step1_confirmed:
        st.markdown("---")
        st.markdown('<div class="step-header">步驟二：條文逐條查核 (Detailed Analysis)</div>', unsafe_allow_html=True)
        st.success(f"✅ 系統確認：此法規「{input_title}」適用於本廠，請繼續執行逐條分析。")
        
        law_content = st.text_area(
            "貼上法規條文內容 (支援多條文)：",
            height=200,
            placeholder="第 1 條：雇主對於機械之原動機、轉軸...\n一、防止危險之發生...",
            value=st.session_state.law_content_buffer,
            key="law_content_input" 
        )
        
        if st.button("📊 生成法規鑑別對照表"):
            if law_content:
                with st.spinner("AI 正在解析條文結構..."):
                    time.sleep(1)
                    df_result = ai_generate_detailed_table(law_content)
                    
                    st.session_state.analysis_df = df_result
                    st.session_state.law_content_buffer = law_content 
                    st.rerun() 
            else:
                st.warning("請先輸入條文內容。")

    if st.session_state.analysis_df is not None:
        # [標題修正] 刪除 (精簡版)
        st.markdown("#### 📑 法規鑑別對照表")
        
        edited_df = st.data_editor(
            st.session_state.analysis_df,
            use_container_width=True,
            num_rows="dynamic",
            key="data_editor_result"
        )
        
        c_btn1, c_btn2 = st.columns([1, 4])
        
        with c_btn1:
            if st.button("🔄 清除重置"):
                st.session_state.step1_confirmed = False
                st.session_state.analysis_df = None
                st.session_state.law_content_buffer = ""
                st.rerun()
                
        with c_btn2:
            if st.button("📝 將此分析立案並送出簽核", type="primary"):
                summary_content = f"針對「{input_title}」進行鑑別，共 {len(edited_df)} 條項目。"
                new_case = {
                    "id": f"CASE-{datetime.date.today().strftime('%Y%m%d')}-{random.randint(100,999)}",
                    "date": datetime.date.today().strftime("%Y-%m-%d"),
                    "source": "AI 法規鑑別",
                    "title": input_title,
                    "content": summary_content,
                    "department": "職安室 / 跨部門",
                    "status": "待簽核",
                    "manager_comment": "",
                    "completion_date": "",
                    "risk_level": "AI 判定"
                }
                st.session_state['audit_records'].insert(0, new_case)
                save_records(st.session_state['audit_records'])
                st.success("✅ 案件已成功立案！請至【合規簽核紀錄】查看。")


# ------------------------------------------------------------------
# 分頁 3: 合規簽核紀錄
# ------------------------------------------------------------------
with tab3:
    st.subheader("📝 合規追蹤與簽核管理")

    with st.expander("➕ 新增定期查核/手動案件 (Manual Entry)", expanded=False):
        with st.form("manual_case_form"):
            col_m1, col_m2 = st.columns(2)
            m_title = col_m1.text_input("案件標題/來源", placeholder="例如：Q1 廠區巡檢")
            m_dept = col_m2.selectbox("負責單位", ["職安室", "工務課", "生產部", "總務課"])
            m_content = st.text_area("缺失/議題內容", placeholder="描述發現的問題...")
            m_suggestion = st.text_area("建議改善措施", placeholder="例如：請盡速修繕...")
            m_risk = st.selectbox("風險等級", ["低", "中", "高"])
            
            submitted = st.form_submit_button("📥 建立案件並生成郵件草稿")
            
            if submitted:
                if m_title and m_content:
                    manual_case = {
                        "id": f"MANUAL-{random.randint(1000,9999)}",
                        "date": datetime.date.today().strftime("%Y-%m-%d"),
                        "source": "手動立案",
                        "title": m_title,
                        "content": m_content,
                        "department": m_dept,
                        "status": "待簽核",
                        "manager_comment": "",
                        "completion_date": "",
                        "risk_level": m_risk,
                        "suggestion": m_suggestion
                    }
                    st.session_state['audit_records'].insert(0, manual_case)
                    save_records(st.session_state['audit_records'])
                    st.success(f"案件 {manual_case['id']} 已建立！")
                    
                    # [優化] 電子郵件草稿內容豐富化
                    deadline = (datetime.date.today() + datetime.timedelta(days=7)).strftime("%Y-%m-%d")
                    draft = f"""
                    主旨：【合規改善通知】{m_title} - 發現潛在風險需改善
                    
                    {m_dept} 主管/同仁 您好：
                    
                    依據本廠 ISO 45001 管理系統程序，近期查核發現以下事項，請貴單位協助確認並改善：
                    
                    📍 案件標題：{m_title}
                    ⚠️ 發現內容：{m_content}
                    🔴 風險評估：{m_risk}
                    💡 建議措施：{m_suggestion}
                    
                    ⏳ 建議改善期限：{deadline}
                    
                    請於期限內回覆改善計畫或完成進度。感謝您的配合！
                    
                    此致
                    職安室 敬上
                    """
                    st.info("📧 郵件草稿已生成：")
                    st.code(draft)
                else:
                    st.error("請填寫完整資訊 (標題與內容為必填)。")

    st.divider()

    # === 區塊 A: 待簽核案件 (Pending) ===
    all_records = st.session_state['audit_records']
    pending_records = [r for r in all_records if r['status'] == '待簽核']
    history_records = [r for r in all_records if r['status'] in ['已核准', '已退回']]

    st.markdown("### 🔔 待簽核案件 (Pending)")
    if not pending_records:
        st.info("目前無待簽核案件。")
    else:
        pending_ids = [r['id'] for r in pending_records]
        selected_id = st.selectbox("選擇處理案件：", pending_ids)
        case = next((r for r in pending_records if r['id'] == selected_id), None)
        
        if case:
            c1, c2 = st.columns([2, 1])
            with c1:
                st.markdown(f"""
                * **來源：** {case['source']}
                * **標題：** {case['title']}
                * **內容摘要：** {case['content']}
                * **負責單位：** {case['department']}
                """)
                
                # [RBAC 控管] 職安室成員視角
                if user_role == "職安室成員":
                    if st.button("📧 生成通知信草稿"):
                        # [優化] 電子郵件草稿內容豐富化
                        deadline = (datetime.date.today() + datetime.timedelta(days=7)).strftime("%Y-%m-%d")
                        r_level = case.get('risk_level', '系統評估')
                        sug = case.get('suggestion', '依據法規或內規辦理')
                        email_draft = f"""
                        主旨：【合規改善通知】{case['title']} - 發現潛在風險需改善
                        
                        {case['department']} 主管/同仁 您好：
                        
                        依據本廠 ISO 45001 管理系統程序，近期查核發現以下事項，請貴單位協助確認並改善：
                        
                        📍 案件標題：{case['title']}
                        ⚠️ 發現內容：{case['content']}
                        🔴 風險評估：{r_level}
                        💡 建議措施：{sug}
                        
                        ⏳ 建議改善期限：{deadline}
                        
                        請於期限內回覆改善計畫或完成進度。感謝您的配合！
                        
                        此致
                        職安室 敬上
                        """
                        st.code(email_draft)
            
            with c2:
                # [RBAC 控管] 職安室主管視角
                if user_role == "職安室主管":
                    st.markdown("#### 主管決策")
                    comment = st.text_area("簽核意見：", key="mgr_comment")
                    col_btn1, col_btn2 = st.columns(2)
                    
                    if col_btn1.button("✅ 核准"):
                        case['status'] = "已核准"
                        case['manager_comment'] = comment if comment else "同意備查"
                        case['completion_date'] = datetime.date.today().strftime("%Y-%m-%d")
                        save_records(st.session_state['audit_records'])
                        st.rerun()
                        
                    if col_btn2.button("❌ 退回"):
                        case['status'] = "已退回"
                        case['manager_comment'] = comment if comment else "資料不全，請補充"
                        case['completion_date'] = datetime.date.today().strftime("%Y-%m-%d")
                        save_records(st.session_state['audit_records'])
                        st.rerun()
                else:
                    st.info("🔒 僅限「職安室主管」進行簽核決策。")

    st.markdown("---")

    # === 區塊 B: 歷史簽核紀錄 (History) ===
    st.markdown("### 🗄️ 稽核證據保存區 (History / Evidence)")
    st.caption("此區域資料僅供 ISO 外部稽核員查閱，顯示已結案之軌跡。")
    
    if history_records:
        df_history = pd.DataFrame(history_records)
        df_display = df_history[[
            'date', 'title', 'department', 'status', 'manager_comment', 'completion_date'
        ]].rename(columns={
            'date': '建立日期',
            'title': '法規/案件名稱',
            'department': '負責單位',
            'status': '最終狀態',
            'manager_comment': '主管簽核意見',
            'completion_date': '完成時間'
        })
        st.dataframe(df_display, use_container_width=True, hide_index=True)
    else:
        st.write("尚無歷史紀錄。")

st.markdown("---")
st.markdown("© 2026 ISO 45001 Smart Compliance System V2.3")