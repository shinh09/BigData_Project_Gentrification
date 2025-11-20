# -*- coding: utf-8 -*-
"""
연도별로 저장된 블로그 포스트 CSV를
postdate(YYYYMMDD)를 기준으로 월별 CSV로 쪼개서 저장하는 스크립트.

예)
  입력 : blog_posts_연남동_명소_2024.csv
  출력 : blog_posts_연남동_명소_202401.csv
        blog_posts_연남동_명소_202402.csv
        ...
"""

import os
import pandas as pd

# ===== 설정 =====
BASE_DIR   = "./data_html/익선동"           # CSV가 있는 폴더
BASE_NAME  = "blog_posts_익선동_명소"  # 파일 이름 공통 부분
YEAR       = 2025                 # 쪼갤 연도
INPUT_FILE = os.path.join(BASE_DIR, f"{BASE_NAME}_{YEAR}.csv")

# 월별 파일을 저장할 폴더 (그냥 BASE_DIR에 저장하고 싶으면 OUTPUT_DIR = BASE_DIR 로 바꿔도 됨)
OUTPUT_DIR = f"./data_html/익선동/{YEAR}" 
# ===============


def main():
    if not os.path.exists(INPUT_FILE):
        raise FileNotFoundError(f"입력 파일을 찾을 수 없습니다: {INPUT_FILE}")

    print(f"[INFO] 연도별 CSV 읽는 중: {INPUT_FILE}")
    df = pd.read_csv(INPUT_FILE, encoding="utf-8-sig")

    if "postdate" not in df.columns:
        raise KeyError("CSV에 'postdate' 컬럼이 없습니다.")

    # postdate를 문자열(YYYYMMDD)로 정리
    df["postdate"] = df["postdate"].astype(str).str.strip()

    # 8자리(YYYYMMDD)만 잘라서 사용 (혹시 모를 이상값 방지용)
    df = df[df["postdate"].str.len() >= 6].copy()

    # year-month 키 (YYYYMM)
    df["yyyymm"] = df["postdate"].str.slice(0, 6)

    # 월별로 그룹 나눠서 저장
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    for yyyymm, df_month in df.groupby("yyyymm"):
        # 해당 연도만 필터 (혹시 다른 연도가 섞여 있을 경우 방지)
        if not yyyymm.startswith(str(YEAR)):
            continue

        out_path = os.path.join(OUTPUT_DIR, f"{BASE_NAME}_{yyyymm}.csv")
        df_month = df_month.drop(columns=["yyyymm"])

        print(f"[SAVE] {yyyymm} → {out_path} (rows: {len(df_month)})")
        df_month.to_csv(out_path, index=False, encoding="utf-8-sig")

    print("[DONE] 월별 CSV 분리 완료.")


if __name__ == "__main__":
    main()
