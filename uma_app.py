import streamlit as st
import pandas as pd
import glob
import os

st.title("血統傾向分析 & 出走馬印判定ツール")

# サイドバー設定
st.sidebar.header("分析条件の設定")
view_mode = st.sidebar.radio("表示モード", ["PC表示", "モバイル表示"])

# データ読み込み
data_dir = "data"
all_files = glob.glob(os.path.join(data_dir, "*.csv"))
df_list = [pd.read_csv(file, encoding="cp932") for file in all_files]
df = pd.concat(df_list, ignore_index=True)

# 条件セレクト
surface = st.sidebar.selectbox("芝・ダート", df["芝・ダ"].dropna().unique())
place = st.sidebar.selectbox("競馬場", df["競馬場"].dropna().unique())
condition = st.sidebar.selectbox("馬場状態", df["馬場状態"].dropna().unique())
distance = st.sidebar.selectbox("距離", sorted(df["距離"].dropna().unique().astype(int)))

# フィルタ
df["着順"] = pd.to_numeric(df["着順"], errors="coerce")
filtered = df[
    (df["芝・ダ"] == surface) &
    (df["競馬場"] == place) &
    (df["馬場状態"] == condition) &
    (df["距離"] == distance)
]

kyakushitsu_list = ["逃げ", "先行", "差し", "追込"]

def aggregate_stats(field):
    df_total = filtered.groupby(field).size().reset_index(name="出走数")
    df_win = filtered[filtered["着順"] == 1].groupby(field).size().reset_index(name="勝利数")
    df_place = filtered[filtered["着順"] <= 3].groupby(field).size().reset_index(name="複勝数")

    merged = df_total.merge(df_win, on=field, how="left").merge(df_place, on=field, how="left")
    merged.fillna(0, inplace=True)

    merged["勝率"] = (merged["勝利数"] / merged["出走数"] * 100).round(1)
    merged["複勝率"] = (merged["複勝数"] / merged["出走数"] * 100).round(1)

    for style in kyakushitsu_list:
        style_place = filtered[(filtered["着順"] <= 3) & (filtered["脚質"] == style)] \
            .groupby(field).size().reset_index(name=f"{style}複勝")
        merged = merged.merge(style_place, on=field, how="left")
        merged[f"{style}複勝"].fillna(0, inplace=True)

    return merged.sort_values("複勝率", ascending=False)

# 集計表示
with st.expander("種牡馬別の複勝成績"):
    sire_stats = aggregate_stats("種牡馬")
    if view_mode == "PC表示":
        st.dataframe(sire_stats)
    else:
        st.dataframe(sire_stats, height=300)

with st.expander("母父馬別の複勝成績"):
    dam_stats = aggregate_stats("母父馬")
    if view_mode == "PC表示":
        st.dataframe(dam_stats)
    else:
        st.dataframe(dam_stats, height=300)

# 出走馬判定
st.header("出走馬判定")
st.sidebar.markdown("### 印の条件（複勝率）")
rank_uma = {
    "◎": st.sidebar.number_input("◎（本命）", min_value=0, max_value=100, value=40),
    "○": st.sidebar.number_input("○（対抗）", min_value=0, max_value=100, value=30),
    "▲": st.sidebar.number_input("▲（単穴）", min_value=0, max_value=100, value=20),
    "△": st.sidebar.number_input("△（抑え）", min_value=0, max_value=100, value=10),
}

st.markdown("⚠️ **読み込ませるCSVデータには以下のカラムが必要です。**  \n`馬名, 種牡馬, 母父馬, 脚質`")

# 出走馬ダウンロード用CSV作成用
race_display = pd.DataFrame()

upload_file = st.file_uploader("出走表CSVをアップロードしてください", type="csv")

if upload_file:
    race_df = pd.read_csv(upload_file, encoding="cp932")

    def get_avg_rate(row):
        sire = row["種牡馬"]
        dam = row["母父馬"]

        sire_rate = sire_stats.loc[sire_stats["種牡馬"] == sire, "複勝率"]
        dam_rate = dam_stats.loc[dam_stats["母父馬"] == dam, "複勝率"]

        sire_val = float(sire_rate.values[0]) if not sire_rate.empty else None
        dam_val  = float(dam_rate.values[0]) if not dam_rate.empty else None

        if sire_val is not None and dam_val is not None:
            return round((sire_val + dam_val) / 2, 1)
        elif sire_val is not None:
            return round(sire_val, 1)
        elif dam_val is not None:
            return round(dam_val, 1)
        else:
            return 0.0

    def get_mark(avg_rate):
        for mark, threshold in sorted(rank_uma.items(), key=lambda x: -x[1]):
            if avg_rate >= threshold:
                return mark
        return ""

    race_df["複勝率"] = race_df.apply(get_avg_rate, axis=1)
    race_df["印"] = race_df["複勝率"].apply(get_mark)

    # 表示する列を限定
    possible_cols = ["番", "馬番", "馬名", "種牡馬", "母父馬", "馬体重", "脚質"]
    used_cols = [col for col in possible_cols if col in race_df.columns]
    display_cols = used_cols + ["複勝率", "印"]
    race_display = race_df[display_cols]

    st.markdown(f"""
    **分析条件：**
    - 芝・ダート: `{surface}`
    - 競馬場: `{place}`
    - 馬場状態: `{condition}`
    - 距離: `{distance}m`
    """)

    st.subheader("出走馬への印（複勝率付き）")
    if view_mode == "PC表示":
        st.dataframe(race_display)
    else:
        st.dataframe(race_display, height=400)

    # CSV保存ボタン
    csv = race_display.to_csv(index=False).encode("cp932")
    st.download_button(
        label="📥 出走馬一覧をCSVで保存",
        data=csv,
        file_name="出走馬印付き一覧.csv",
        mime="text/csv"
    )
