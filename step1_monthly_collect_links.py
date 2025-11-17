# -*- coding: utf-8 -*-
# 네이버 블로그 검색 결과에서 '한남동 명소' 키워드로
# 지정된 연도(예: 2025) 전체 날짜를 순회하며
# 월별로 링크 CSV 저장 (예: links_한남동_명소_202501.csv)

import os, re, time, random
import pandas as pd
from datetime import datetime, timedelta
from urllib.parse import quote
from seleniumwire import webdriver
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

# ===== 설정 =====
QUERY       = "신사동 명소"
YEAR        = 2022
SAVE_DIR    = "./data_html/신사동_명소/2022/links"
WAIT_SEC    = 25
PAUSE       = (0.8, 1.6)
SCROLL_STEPS= 4
# ===============

os.makedirs(SAVE_DIR, exist_ok=True)

def human_pause(a=1.0, b=2.0): time.sleep(random.uniform(a,b))
def clean(s): return re.sub(r"\s+", " ", (s or "").strip())

def sanitize_for_fname(s: str) -> str:
    s = s.strip().replace(" ", "_")
    s = re.sub(r"[^\w\-\.가-힣]+", "", s)
    return s

def build_driver():
    opts = uc.ChromeOptions()
    opts.add_argument("--lang=ko-KR")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1400,900")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
    )
    return webdriver.Chrome(options=opts, seleniumwire_options={"verify_ssl": True, "disable_encoding": True})

def build_search_url(q, day):
    f = day.strftime("%Y%m%d")
    nso = f"so:dd,p:from{f}to{f}"
    return f"https://search.naver.com/search.naver?where=blog&sm=tab_opt&ssc=tab.blog.all&query={quote(q)}&nso={nso}"

TITLE_SELECTORS = [
    "a.api_txt_lines.total_tit",
    "a.total_tit",
    "a.title_link",
    "div.total_wrap a[href*='blog.naver.com']",
    "a[href*='blog.naver.com']",
]

def click_blog_tab_if_any(driver):
    for s in [
        "a[role='tab'][href*='where=blog']",
        "a[aria-selected='false'][href*='where=blog']",
        "a[href*='where=blog'].tab",
        "a[href*='where=blog']",
    ]:
        try:
            tabs = driver.find_elements(By.CSS_SELECTOR, s)
            if tabs:
                tabs[0].click()
                time.sleep(1.0)
                return True
        except Exception:
            pass
    return False

def ensure_results_ready(driver):
    try:
        WebDriverWait(driver, WAIT_SEC).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        click_blog_tab_if_any(driver)

        for _ in range(2):
            driver.execute_script("window.scrollBy(0, document.body.scrollHeight*0.5);")
            time.sleep(0.8)
            driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(0.4)

        def ok(d):
            for s in TITLE_SELECTORS:
                if d.find_elements(By.CSS_SELECTOR, s):
                    return True
            return "검색결과가 없습니다" in d.page_source

        WebDriverWait(driver, WAIT_SEC).until(ok)
        return True
    except Exception:
        return False

def click_next(driver):
    for sel in ["a.btn_next", "a.pg_next", "a.sc_page_next", "a[aria-label='다음']"]:
        btns = driver.find_elements(By.CSS_SELECTOR, sel)
        if btns and btns[0].is_displayed():
            try:
                btns[0].click()
                return True
            except Exception:
                pass
    try:
        cur = driver.find_element(By.CSS_SELECTOR, "div.sc_page a[aria-current='page']")
        cur_num = int(re.sub(r"\D", "", cur.text))
        nxt = driver.find_element(
            By.XPATH, f"//div[contains(@class,'sc_page')]//a[normalize-space(text())='{cur_num+1}']"
        )
        nxt.click()
        return True
    except Exception:
        return False

def list_seeds_for_day(driver, day):
    url = build_search_url(QUERY, day)
    print(f"\n📅 {day:%Y-%m-%d} 링크 수집: {url}")
    driver.get(url)
    if not ensure_results_ready(driver):
        print("⚠️ 초기 로딩 실패")
        return []

    seeds, seen = [], set()
    page_idx = 1
    while True:
        for _ in range(SCROLL_STEPS):
            driver.execute_script("window.scrollBy(0, document.body.scrollHeight*0.85);")
            human_pause(*PAUSE)

        anchors = []
        for sel in TITLE_SELECTORS:
            anchors = driver.find_elements(By.CSS_SELECTOR, sel)
            if anchors:
                break

        for a in anchors:
            href = a.get_attribute("href") or ""
            if not href or ("blog.naver.com" not in href and "m.blog.naver.com" not in href):
                continue
            if href in seen:
                continue
            seen.add(href)
            title = clean(a.text) or clean(a.get_attribute("title") or "")
            seeds.append({"date": day.strftime("%Y-%m-%d"), "title": title, "link": href})

        if not click_next(driver):
            break
        page_idx += 1
        human_pause(*PAUSE)

    print(f"🔗 수집 링크: {len(seeds)}건")
    return seeds

def save_month_csv(rows, month_key):
    if not rows:
        print(f"📦 {month_key}: 저장할 데이터 없음")
        return
    df = pd.DataFrame(rows, columns=["date", "title", "link"])
    before = len(df)
    df = df.drop_duplicates(subset=["link"]).reset_index(drop=True)
    after = len(df)
    print(f"🧹 {month_key}: 중복 제거 {before-after}건 → 최종 {after}건")

    qslug = sanitize_for_fname(QUERY)
    out_path = os.path.join(SAVE_DIR, f"links_{qslug}_{month_key}.csv")
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"✅ 월 통합 CSV 저장 → {out_path}")

def main():
    driver = build_driver()
    try:
        start_day = datetime(YEAR, 1, 1)
        end_day = datetime(YEAR, 12, 31)
        day = start_day

        current_month_key = day.strftime("%Y%m")
        month_rows = []

        while day <= end_day:
            day_month_key = day.strftime("%Y%m")
            if day_month_key != current_month_key:
                save_month_csv(month_rows, current_month_key)
                month_rows = []
                current_month_key = day_month_key

            rows = list_seeds_for_day(driver, day)
            month_rows.extend(rows)

            day += timedelta(days=1)

        save_month_csv(month_rows, current_month_key)

    finally:
        driver.quit()

if __name__ == "__main__":
    main()
