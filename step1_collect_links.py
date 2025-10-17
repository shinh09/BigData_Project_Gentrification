# -*- coding: utf-8 -*-
# 네이버 블로그 검색 결과에서 '성수동 핫플' 해당 '일자'의 제목/링크를 수집하되,
# CSV 저장은 '월별'로 통합 저장 (예: 2025-01 전체 → links_성수동_핫플_202501.csv)

import os, re, time, random
import pandas as pd
from datetime import datetime, timedelta
from urllib.parse import quote
from seleniumwire import webdriver
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

# ===== 설정 =====
QUERY       = "성수동 명소"
DATE_START  = datetime(2025, 1, 1)
DATE_END    = datetime(2025, 1, 31)
SAVE_DIR    = "./data_html"
WAIT_SEC    = 25
PAUSE       = (0.8, 1.6)
SCROLL_STEPS= 4
# ===============

os.makedirs(SAVE_DIR, exist_ok=True)

def human_pause(a=1.0, b=2.0): time.sleep(random.uniform(a,b))
def clean(s): return re.sub(r"\s+", " ", (s or "").strip())

def sanitize_for_fname(s: str) -> str:
    s = s.strip().replace(" ", "_")
    s = re.sub(r"[^\w\-\.가-힣]+", "", s)  # 한글/영문/숫자/언더스코어/하이픈/점만
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
    nso = f"so:dd,p:from{f}to{f}"  # 해당 '하루'만
    return f"https://search.naver.com/search.naver?where=blog&sm=tab_opt&ssc=tab.blog.all&query={quote(q)}&nso={nso}"

def dump_debug(driver, label):
    html_path = os.path.join(SAVE_DIR, f"DEBUG_{label}.html")
    png_path  = os.path.join(SAVE_DIR, f"DEBUG_{label}.png")
    try:
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
    except Exception:
        pass
    try:
        driver.save_screenshot(png_path)
    except Exception:
        pass
    print(f"   ↳ 디버그 저장: {html_path}, {png_path}")

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

        # lazy-load 유도
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
        dump_debug(driver, f"{sanitize_for_fname(QUERY)}_{day:%Y%m%d}_noresults_init")
        return []

    seeds, seen = [], set()
    page_idx = 1
    while True:
        # 충분히 스크롤해서 추가 로딩
        for _ in range(SCROLL_STEPS):
            driver.execute_script("window.scrollBy(0, document.body.scrollHeight*0.85);")
            human_pause(*PAUSE)

        anchors = []
        for sel in TITLE_SELECTORS:
            anchors = driver.find_elements(By.CSS_SELECTOR, sel)
            if anchors:
                break

        if not anchors:
            print(f"⚠️ p{page_idx} 링크 셀렉터 실패")
            dump_debug(driver, f"{sanitize_for_fname(QUERY)}_{day:%Y%m%d}_p{page_idx}_no_titles")

        for a in anchors:
            href = a.get_attribute("href") or ""
            if not href:
                continue
            if ("blog.naver.com" not in href) and ("m.blog.naver.com" not in href):
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
    if len(seeds) == 0:
        dump_debug(driver, f"{sanitize_for_fname(QUERY)}_{day:%Y%m%d}_no_seeds")
    return seeds

def save_month_csv(rows, month_key):
    """rows: list of dicts(date,title,link), month_key: 'YYYYMM'"""
    if not rows:
        print(f"📦 {month_key}: 저장할 데이터 없음")
        return
    df = pd.DataFrame(rows, columns=["date", "title", "link"])
    # 월 단위 중복 제거 (link 기준)
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
        day = DATE_START
        current_month_key = day.strftime("%Y%m")
        month_rows = []  # 현재 월 누적 버퍼

        while day <= DATE_END:
            day_month_key = day.strftime("%Y%m")
            # 월이 바뀌면 이전 월 저장 후 리셋
            if day_month_key != current_month_key:
                save_month_csv(month_rows, current_month_key)
                month_rows = []
                current_month_key = day_month_key

            # 일별 수집
            rows = list_seeds_for_day(driver, day)
            month_rows.extend(rows)

            day += timedelta(days=1)

        # 마지막 월 저장
        save_month_csv(month_rows, current_month_key)

    finally:
        driver.quit()

if __name__ == "__main__":
    main()
