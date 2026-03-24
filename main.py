import streamlit as st
import pandas as pd
import random
import gspread
from google.oauth2.service_account import Credentials
import time

# --- 頁面配置與 CSS 優化 ---
st.set_page_config(
    page_title="Deutsch Meisterschaft", page_icon="🇩🇪", layout="centered"
)
# 在 CSS 後面加上這段 JavaScript
st.markdown(
    """
    <script>
    function speakGerman(text) {
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = 'de-DE'; // 設定為德語
        utterance.rate = 0.9;     // 語速稍微放慢，方便聽清發音細節
        window.speechSynthesis.speak(utterance);
    }
    </script>
    """,
    unsafe_allow_html=True,
)
st.markdown(
    """
    <style>
    .stButton>button { width: 100%; border-radius: 12px; height: 3.5em; font-size: 16px; font-weight: 600; margin-bottom: 8px; }
    .question-card { background-color: #ffffff; padding: 25px; border-radius: 20px; border: 1px solid #e0e0e0; box-shadow: 0 4px 6px rgba(0,0,0,0.05); text-align: center; }
    .word-display { font-size: 36px; font-weight: 800; margin-bottom: 5px; }
    .meaning-display { font-size: 20px; color: #4B5563; margin-bottom: 5px; font-weight: 500; }
    .detail-display { font-size: 16px; color: #6B7280; margin-top: 10px; line-height: 1.6; }
    .stats-container { display: flex; justify-content: space-around; background-color: #f8fafc; padding: 15px; border-radius: 15px; margin-bottom: 20px; border: 1px solid #e2e8f0; }
    .stats-item { text-align: center; }
    .stats-value { font-size: 20px; font-weight: bold; color: #1E3A8A; }
    .stats-label { font-size: 12px; color: #64748b; text-transform: uppercase; }
    .color-der { color: #1E3A8A; }
    .color-die { color: #ef4444; }
    .color-das { color: #22c55e; }
    .color-default { color: #334155; }
    </style>
    """,
    unsafe_allow_html=True,
)


# --- 核心資料抓取邏輯 ---
@st.cache_data(ttl=300)
def fetch_google_sheet_data():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=scope
    )
    client = gspread.authorize(creds)
    sh = client.open("Deutsch")

    def process_nomen_col(start_row, word_col, mean_col, plural_col):
        data = []
        all_nomen = sh.worksheet("名詞").get_all_values()
        for r in range(start_row - 1, len(all_nomen)):
            row = all_nomen[r]
            if len(row) > max(word_col, mean_col, plural_col) and row[word_col]:
                data.append(
                    {
                        "德文單字": row[word_col].strip(),
                        "中文意思": row[mean_col].strip(),
                        "複數型態": (
                            row[plural_col].strip()
                            if row[plural_col]
                            else "kein Plural"
                        ),
                    }
                )
        return data

    nomen_dict = {
        "陽性": process_nomen_col(4, 0, 1, 2),
        "陰性": process_nomen_col(4, 3, 4, 5),
        "中性": process_nomen_col(4, 6, 7, 8),
    }

    def process_verb_col(start_row, word_col, mean_col, past_col, p2_col):
        data = []
        all_verb = sh.worksheet("動詞").get_all_values()
        for r in range(start_row - 1, len(all_verb)):
            row = all_verb[r]
            if len(row) > max(word_col, mean_col, past_col, p2_col) and row[word_col]:
                data.append(
                    {
                        "德文單字": row[word_col].strip(),
                        "中文意思": row[mean_col].strip(),
                        "過去式": row[past_col].strip(),
                        "過去分詞": row[p2_col].strip(),
                    }
                )
        return data

    verben_dict = {
        "強變化": process_verb_col(3, 0, 1, 2, 3),
        "弱變化": process_verb_col(3, 4, 5, 6, 7),
    }
    adj_vals = sh.worksheet("形容詞").get_all_values()
    adjektiv_list = [
        {"德文單字": r[0].strip(), "中文意思": r[1].strip()}
        for r in adj_vals[2:]
        if len(r) >= 2 and r[0]
    ]
    pro_vals = sh.worksheet("代名詞").get_all_values()
    pronomen_list = [
        {"德文單字": r[0].strip(), "中文意思": r[1].strip()}
        for r in pro_vals[2:]
        if len(r) >= 2 and r[0]
    ]

    return nomen_dict, verben_dict, adjektiv_list, pronomen_list


# --- 初始化 ---
try:
    nomen, verben, adjektiv, pronomen = fetch_google_sheet_data()
except Exception as e:
    st.error(f"資料抓取失敗: {e}")
    st.stop()

bestimmter_artikel = [
    {
        "格位": "主格 (Nominativ)",
        "陽性": "der",
        "中性": "das",
        "陰性": "die",
        "複數": "die",
    },
    {
        "格位": "受格 (Akkusativ)",
        "陽性": "den",
        "中性": "das",
        "陰性": "die",
        "複數": "die",
    },
    {
        "格位": "與格 (Dativ)",
        "陽性": "dem",
        "中性": "dem",
        "陰性": "der",
        "複數": "den",
    },
    {
        "格位": "屬格 (Genitiv)",
        "陽性": "des",
        "中性": "des",
        "陰性": "der",
        "複數": "der",
    },
]

states = [
    "quiz_state",
    "answered",
    "is_correct",
    "total_count",
    "wrong_count",
    "wrong_book",
    "current_cat",
]
default_vals = [None, False, None, 0, 0, [], "全部"]
for s, v in zip(states, default_vals):
    if s not in st.session_state:
        st.session_state[s] = v


def set_question(cat_name):
    st.session_state.answered = False
    st.session_state.is_correct = None
    st.session_state.current_cat = cat_name
    quiz_data = {}

    if cat_name == "名詞":
        g = random.choice(["陽性", "陰性", "中性"])
        item = random.choice(nomen[g])
        quiz_data = {
            "cat": "N",
            "data": item,
            "gender": g,
            "type": random.choice(["填空", "意填空", "意選擇", "猜性別"]),
        }
        if quiz_data["type"] == "意選擇":
            flat = [i["中文意思"] for sub in nomen.values() for i in sub]
            quiz_data["options"] = random.sample(flat, 4) + [item["中文意思"]]
            random.shuffle(quiz_data["options"])
    elif cat_name == "動詞":
        v_type = random.choice(["強變化", "弱變化"])
        item = random.choice(verben[v_type])
        quiz_data = {
            "cat": "V",
            "data": item,
            "type": random.choice(["填空", "意填空", "意選擇", "過去回答"]),
        }
        if quiz_data["type"] == "意選擇":
            flat = [i["中文意思"] for sub in verben.values() for i in sub]
            quiz_data["options"] = random.sample(flat, 4) + [item["中文意思"]]
            random.shuffle(quiz_data["options"])
    elif cat_name in ["形容詞", "代名詞"]:
        source = adjektiv if cat_name == "形容詞" else pronomen
        item = random.choice(source)
        quiz_data = {
            "cat": "A" if cat_name == "形容詞" else "P",
            "data": item,
            "type": random.choice(["填空", "意填空", "意選擇"]),
        }
        if quiz_data["type"] == "意選擇":
            quiz_data["options"] = random.sample(
                [i["中文意思"] for i in source], min(len(source), 4)
            ) + [item["中文意思"]]
            random.shuffle(quiz_data["options"])
    elif cat_name == "冠詞":
        row = random.choice(bestimmter_artikel)
        gender_key = random.choice(["陽性", "中性", "陰性", "複數"])
        quiz_data = {
            "cat": "ART",
            "case": row["格位"],
            "gender": gender_key,
            "ans": row[gender_key],
        }

    st.session_state.quiz_state = quiz_data


def record_result(correct, item_data):
    st.session_state.total_count += 1
    st.session_state.answered = True
    st.session_state.is_correct = correct
    if not correct:
        st.session_state.wrong_count += 1
        if item_data not in st.session_state.wrong_book:
            st.session_state.wrong_book.append(item_data)
    st.rerun()  # 立即刷新以顯示結果


# --- 側邊欄 ---
with st.sidebar:
    st.title("🎮 導覽選單")
    for btn_text, cat in [
        ("🏠 名詞", "名詞"),
        ("🏃 動詞", "動詞"),
        ("🎨 形容詞", "形容詞"),
        ("📏 冠詞", "冠詞"),
    ]:
        if st.button(btn_text):
            set_question(cat)
    if st.button("🎲 全部"):
        set_question(random.choice(["名詞", "動詞", "形容詞", "代名詞", "冠詞"]))
    st.divider()
    if st.button("📕 查看錯題本"):
        st.session_state.show_wrong = True
    if st.button("🔄 同步雲端資料"):
        st.cache_data.clear()
        st.rerun()

st.title("🇩🇪 Vokabel Meister")
st.markdown(
    f"""
    <div class="stats-container">
        <div class="stats-item"><div class="stats-value">{st.session_state.total_count}</div><div class="stats-label">總題數</div></div>
        <div class="stats-item"><div class="stats-value" style="color: #22c55e;">{st.session_state.total_count - st.session_state.wrong_count}</div><div class="stats-label">答對</div></div>
        <div class="stats-item"><div class="stats-value" style="color: #ef4444;">{st.session_state.wrong_count}</div><div class="stats-label">錯誤</div></div>
    </div>
""",
    unsafe_allow_html=True,
)

# --- 主程式 ---
if st.session_state.quiz_state:
    q = st.session_state.quiz_state
    st.markdown('<div class="question-card">', unsafe_allow_html=True)

    if not st.session_state.answered:
        # 使用 st.form 解決「按兩下」問題
        with st.form(key="quiz_form"):
            if q["cat"] == "N":
                data, g_art = (
                    q["data"],
                    {"陽性": "der", "陰性": "die", "中性": "das"}[q["gender"]],
                )
                if q["type"] == "填空":
                    st.write(f"中文意思：{data['中文意思']}")
                    a1 = st.text_input(
                        f"單數 ({g_art}): {data['德文單字'][0]}..."
                    ).strip()
                    a2 = st.text_input(f"複數型態: {data['複數型態'][0]}...").strip()
                    if st.form_submit_button("檢查答案"):
                        record_result(
                            a1.lower() == data["德文單字"].lower()
                            and a2.lower() == data["複數型態"].lower(),
                            data,
                        )
                elif q["type"] == "意填空":
                    st.markdown(
                        f'<div class="word-display color-default">{g_art} {data["德文單字"]}</div>',
                        unsafe_allow_html=True,
                    )
                    ac = st.text_input("輸入中文意思：")
                    if st.form_submit_button("提交"):
                        record_result(ac and ac in data["中文意思"], data)
                elif q["type"] == "猜性別":
                    st.markdown(
                        f'<div class="word-display color-default">{data["德文單字"]}</div>',
                        unsafe_allow_html=True,
                    )
                    st.write(f"({data['中文意思']})")
                    # 猜性別題型在 form 中需使用下拉選單或單選，因為按鈕在 form 中會立即提交
                    choice = st.radio(
                        "選擇性別：", ["der", "die", "das"], horizontal=True
                    )
                    if st.form_submit_button("確認"):
                        ans_map = {"der": "陽性", "die": "陰性", "das": "中性"}
                        record_result(ans_map[choice] == q["gender"], data)
                elif q["type"] == "意選擇":
                    st.markdown(
                        f'<div class="word-display color-default">{g_art} {data["德文單字"]}</div>',
                        unsafe_allow_html=True,
                    )
                    choice = st.radio("選擇正確意思：", q["options"])
                    if st.form_submit_button("提交答案"):
                        record_result(choice == data["中文意思"], data)

            elif q["cat"] == "V":
                data = q["data"]
                if q["type"] == "填空":
                    st.write(f"意為：{data['中文意思']}")
                    av = st.text_input(f"德文單字：{data['德文單字'][0]}...").strip()
                    if st.form_submit_button("確認"):
                        record_result(av.lower() == data["德文單字"].lower(), data)
                elif q["type"] == "過去回答":
                    st.markdown(
                        f'<div class="word-display color-default">{data["德文單字"]}</div>',
                        unsafe_allow_html=True,
                    )
                    v1 = st.text_input("過去式 (Präteritum)").strip()
                    v2 = st.text_input("過去分詞 (Partizip II)").strip()
                    if st.form_submit_button("提交"):
                        record_result(
                            v1.lower() == data["過去式"].lower()
                            and v2.lower() == data["過去分詞"].lower(),
                            data,
                        )
                elif q["type"] == "意填空":
                    st.markdown(
                        f'<div class="word-display color-default">{data["德文單字"]}</div>',
                        unsafe_allow_html=True,
                    )
                    acv = st.text_input("輸入中文意思：")
                    if st.form_submit_button("提交"):
                        record_result(acv and acv in data["中文意思"], data)
                elif q["type"] == "意選擇":
                    st.markdown(
                        f'<div class="word-display color-default">{data["德文單字"]}</div>',
                        unsafe_allow_html=True,
                    )
                    choice = st.radio("選擇意思：", q["options"])
                    if st.form_submit_button("提交"):
                        record_result(choice == data["中文意思"], data)

            elif q["cat"] in ["A", "P"]:
                data = q["data"]
                st.markdown(
                    f'<div class="word-display color-default">{data["德文單字"] if q["type"] != "填空" else "填入德文單字"}</div>',
                    unsafe_allow_html=True,
                )
                if q["type"] == "填空":
                    st.write(f"意為：{data['中文意思']}")
                    aa = st.text_input(f"德文單字：{data['德文單字'][0]}...").strip()
                    if st.form_submit_button("確認"):
                        record_result(aa.lower() == data["德文單字"].lower(), data)
                elif q["type"] == "意填空":
                    aca = st.text_input("輸入中文意思：")
                    if st.form_submit_button("提交"):
                        record_result(aca and aca in data["中文意思"], data)
                elif q["type"] == "意選擇":
                    choice = st.radio("選擇意思：", q["options"])
                    if st.form_submit_button("提交"):
                        record_result(choice == data["中文意思"], data)

            elif q["cat"] == "ART":
                display_title = f"{q['gender']} {q['case']}"
                st.markdown(
                    f'<div class="word-display color-default">{display_title}</div>',
                    unsafe_allow_html=True,
                )
                # st.subheader(f"性別/複數：{q['gender']}")
                art_in = st.text_input("請輸入正確冠詞：").strip()
                if st.form_submit_button("對答案"):
                    record_result(
                        art_in.lower() == q["ans"].lower(),
                        {"格位": q["case"], "答案": q["ans"]},
                    )

    else:
        # --- B. 顯示詳細資訊卡 (Answered) ---
        if q["cat"] == "N":
            data = q["data"]
            g_art = {"陽性": "der", "陰性": "die", "中性": "das"}[q["gender"]]
            word_to_speak = f"{g_art} {data['德文單字']}" # 名詞連冠詞一起念
            g_class = {"陽性": "color-der", "陰性": "color-die", "中性": "color-das"}[
                q["gender"]
            ]
            title_html = (
                f'<div class="word-display {g_class}">{g_art} {data["德文單字"]}</div>'
            )
            detail_html = (
                f'<div class="meaning-display">{data["中文意思"]}</div>'
                f'<div class="detail-display"><b>複數：</b>{data["複數型態"]}<br><b>詞性：</b>{q["gender"]}</div>'
            )
        elif q["cat"] == "V":
            data = q["data"]
            word_to_speak = data["德文單字"]
            title_html = f'<div class="word-display color-der">{data["德文單字"]}</div>'
            detail_html = (
                f'<div class="meaning-display">{data["中文意思"]}</div>'
                f'<div class="detail-display"><b>過去式：</b>{data["過去式"]}<br><b>過去分詞：</b>{data["過去分詞"]}</div>'
            )
        elif q["cat"] in ["A", "P"]:
            data = q["data"]
            word_to_speak = data["德文單字"]
            title_html = f'<div class="word-display color-der">{data["德文單字"]}</div>'
            detail_html = f'<div class="meaning-display">{data["中文意思"]}</div>'
        elif q["cat"] == "ART":
            word_to_speak = q["ans"]
            title_html = f'<div class="word-display color-der">{q["ans"]}</div>'
            detail_html = f'<div class="meaning-display">{q["case"]}</div><div class="detail-display">對象：{q["gender"]}</div>'
        if word_to_speak:
            # 建立一個隱藏的 img 標籤，利用 onerror 立即執行 JS
            # 這種方式是在「主窗口」執行，能避開 iframe 的語音限制
            js_code = f"""
                <img src="x" onerror='
                    const msg = new SpeechSynthesisUtterance("{word_to_speak}");
                    msg.lang = "de-DE";
                    msg.rate = 0.9;
                    window.speechSynthesis.speak(msg);
                ' style="display:none;">
            """
            st.markdown(js_code, unsafe_allow_html=True)
        st.markdown(title_html, unsafe_allow_html=True)
        st.markdown(detail_html, unsafe_allow_html=True)
        st.divider()

        if st.session_state.is_correct:
            st.success("🎉 Richtig!")
        else:
            st.error("❌ Falsch! 再接再厲")

        if st.button("下一題 ➡️", type="primary"):
            set_question(st.session_state.current_cat)
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

# 錯題本...
if "show_wrong" in st.session_state and st.session_state.show_wrong:
    with st.expander("📝 我的錯題紀錄", expanded=True):
        if not st.session_state.wrong_book:
            st.write("目前沒有錯誤紀錄！")
        else:
            st.table(pd.DataFrame(st.session_state.wrong_book))
        if st.button("關閉錯題本"):
            st.session_state.show_wrong = False
            st.rerun()
