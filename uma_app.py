import streamlit as st
import pandas as pd
import glob
import os

st.title("血統傾向分析 & 出走馬印判定ツール")

# サイドバー設定
st.sidebar.header("分析条件の設定")

# データの読み込み（dataフォルダ内の複数CSVを統合）
data_dir = "data"
all_files = glob.glob(os.path.join(data_dir, "*.csv"))
df_list = []
for file in all_files:
    df = pd.read_csv(file, encoding="cp932")
    df_list.append(df)
df = pd.concat(df_list, ignore_index=True)

# 条件セレクトボックス（脚質は削除）
surface = st.sidebar.selectbox("芝・ダート", df["芝・ダ"].dropna().unique())
place = st.sidebar.selectbox("競馬場", df["競馬場"].dropna().unique())
condition = st.sidebar.selectbox("馬場状態", df["馬場状態"].dropna().unique())
distance = st.sidebar.selectbox("距離", sorted(df["距離"].dropna().unique().astype(int)))

# フィルタ処理（脚質除外）
filtered = df[
    (df["芝・ダ"] == surface) &
    (df["競馬場"] == place) &
    (df["馬場状態"] == condition) &
    (df["距離"] == distance)
]

# 着順を数値に変換
filtered["着順"] = pd.to_numeric(filtered["着順"], errors="coerce")

# 脚質リスト（固定）
kyakushitsu_list = ["逃げ", "先行", "差し", "追込"]

# 複勝率と脚質別複勝数を含めた集計関数
def aggregate_stats(field):
    df_total = filtered.groupby(field).size().reset_index(name="出走数")
    df_win = filtered[filtered["着順"] == 1].groupby(field).size().reset_index(name="勝利数")
    df_place = filtered[filtered["着順"] <= 3].groupby(field).size().reset_index(name="複勝数")
    
    merged = df_total.merge(df_win, on=field, how="left").merge(df_place, on=field, how="left")
    merged.fillna(0, inplace=True)
    
    merged["勝率"] = (merged["勝利数"] / merged["出走数"] * 100).round(1)
    merged["複勝率"] = (merged["複勝数"] / merged["出走数"] * 100).round(1)

    # 脚質別複勝数を列として追加
    for style in kyakushitsu_list:
        style_place = filtered[(filtered["着順"] <= 3) & (filtered["脚質"] == style)].groupby(field).size().reset_index(name=f"{style}複勝")
        merged = merged.merge(style_place, on=field, how="left")
        merged[f"{style}複勝"].fillna(0, inplace=True)

    return merged.sort_values("複勝率", ascending=False)

# 表示
st.subheader("種牡馬別の複勝成績")
sire_stats = aggregate_stats("種牡馬")
st.dataframe(sire_stats)

st.subheader("母父馬別の複勝成績")
dam_stats = aggregate_stats("母父馬")
st.dataframe(dam_stats)

# --- 出走馬印判定 ---

st.header("出走馬判定")

# 印の閾値設定
st.sidebar.markdown("### 印の条件（複勝率）")
rank_uma = {
    "◎": st.sidebar.number_input("◎（本命）", min_value=0, max_value=100, value=40),
    "○": st.sidebar.number_input("○（対抗）", min_value=0, max_value=100, value=30),
    "▲": st.sidebar.number_input("▲（単穴）", min_value=0, max_value=100, value=20),
    "△": st.sidebar.number_input("△（抑え）", min_value=0, max_value=100, value=10),
}

# 出走表CSVアップロード
upload_file = st.file_uploader("出走表CSVをアップロードしてください", type="csv")

if upload_file:
    race_df = pd.read_csv(upload_file, encoding="cp932")

    def get_mark(row):
        sire = row["種牡馬"]
        dam = row["母父馬"]
        
        sire_rate = sire_stats.loc[sire_stats["種牡馬"] == sire, "複勝率"]
        dam_rate = dam_stats.loc[dam_stats["母父馬"] == dam, "複勝率"]
        
        max_rate = max(
            float(sire_rate.values[0]) if not sire_rate.empty else 0,
            float(dam_rate.values[0]) if not dam_rate.empty else 0
        )

        for mark, threshold in sorted(rank_uma.items(), key=lambda x: -x[1]):
            if max_rate >= threshold:
                return mark
        return ""

    race_df["印"] = race_df.apply(get_mark, axis=1)

    # 選択中条件の表示
    st.markdown(f"""
    **分析条件：**
    - 芝・ダート: `{surface}`
    - 競馬場: `{place}`
    - 馬場状態: `{condition}`
    - 距離: `{distance}m`
    """)

    st.subheader("出走馬への印")
    st.dataframe(race_df)
