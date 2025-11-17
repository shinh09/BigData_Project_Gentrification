# -*- coding: utf-8 -*-
# STEP 2: 특정 키워드에 대해 YEAR 전체(1~12월) Step1 결과를 자동으로 상세 크롤링

import os, re, time, random
import pandas as pd
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs, urljoin

from seleniumwire import webdriver
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ===== 사용자 설정 =====
QUERY       = "신사동 명소"
YEAR        = 2022
STEP1_DIR   = "./data_html/신사동 명소/2022/links"                      # Step1 결과 위치
STEP2_DIR   = "./data_html/신사동_명소/2022/blog_posts" # Step2 저장 폴더
WAIT_SEC    = 30
PAUSE       = (1.0, 2.0)
PROBE_DEBUG = False
# =====================

os.makedirs(STEP2_DIR, exist_ok=True)


# -----------------------------------
# 기존 코드 그대로 (생략 없이 유지)
# -----------------------------------

def human_pause(a=1.0, b=2.0): time.sleep(random.uniform(a,b))
def clean(s):
    import re
    return re.sub(r"\s+", " ", (s or "").strip())

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

POST_URL_RE = re.compile(
    r"^https?://(?:(?:m\.)?blog\.naver\.com/[^/]+/\d+|blog\.naver\.com/PostView\.naver\?.*?logNo=\d+)",
    re.IGNORECASE,
)
def is_post_url(u: str) -> bool:
    return bool(POST_URL_RE.match(u or ""))

def goto_post_view(driver, url):
    driver.get(url); human_pause(*PAUSE)
    host = urlparse(driver.current_url).netloc.lower()
    if "m.blog.naver.com" in host:
        return True
    try:
        WebDriverWait(driver, WAIT_SEC).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "iframe#mainFrame"))
        )
        frame = driver.find_element(By.CSS_SELECTOR, "iframe#mainFrame")
        src = frame.get_attribute("src")
        if src:
            if src.startswith("//"): src = "https:" + src
            elif src.startswith("/"): src = urljoin("https://blog.naver.com", src)
            driver.get(src); human_pause(*PAUSE)
            return True
    except:
        pass
    if "PostView" in driver.current_url:
        return True
    return False

def extract_ids(u):
    p = urlparse(u)
    author_id = post_id = ""
    if "m.blog.naver.com" in p.netloc:
        parts = [x for x in p.path.split("/") if x]
        if len(parts) >= 2:
            author_id, post_id = parts[0], parts[1]
    elif "PostView.naver" in p.path:
        q = parse_qs(p.query)
        author_id = (q.get("blogId") or [""])[0]
        post_id   = (q.get("logNo")  or [""])[0]
    return author_id, post_id

def get_first_text(driver, selectors):
    for css in selectors:
        try:
            el = driver.find_element(By.CSS_SELECTOR, css)
            txt = clean(el.text)
            if txt: return txt
        except:
            pass
    return ""

def find_roots(driver):
    cands = [
        "div.se-main-container","div.se_component_wrap","#postViewArea","#postListBody",
        "div#content-area","div#viewTypeSelector","div#_post_content",
        "div.se_textView","article"
    ]
    els = []
    for css in cands:
        els.extend(driver.find_elements(By.CSS_SELECTOR, css))
    return els or [driver.find_element(By.TAG_NAME, "body")]

def normalize_hashtag(t: str) -> str:
    t = (t or "").strip()
    t = re.sub(r"\s+", "", t)
    return t if t.startswith("#") else "#" + t

def extract_body_tags_imgs_videos(driver):
    bodies, tags, imgs, vids = [], [], [], []
    for root in find_roots(driver):
        try:
            t = clean(root.text)
            if t: bodies.append(t)
        except:
            pass
        for css in [
            "span.se_hashtag","a.link_tag","a[href*='query=%23']",
            ".tag_area a",".post_tag a"
        ]:
            for el in root.find_elements(By.CSS_SELECTOR, css):
                raw = (el.text or "").strip()
                if raw:
                    ht = normalize_hashtag(raw)
                    if ht not in tags: tags.append(ht)
        for img in root.find_elements(By.CSS_SELECTOR, "img"):
            s = img.get_attribute("src")
            if s and s.startswith("http") and s not in imgs:
                imgs.append(s)
        for ifr in root.find_elements(By.CSS_SELECTOR, "iframe"):
            s = ifr.get_attribute("src") or ""
            if any(k in s for k in ["youtube","tv.naver","vimeo"]):
                vids.append(s)
    body = max(bodies, key=len) if bodies else ""
    return body[:200000], tags, imgs, vids

def extract_bloggername(driver, fallback=""):
    sels = [
        "#nickNameArea","a.link.pcol2","span.nick","span.nick_name",
        "div.se_profile a","div.bloger > a"
    ]
    for s in sels:
        try:
            txt = clean(driver.find_element(By.CSS_SELECTOR, s).text)
            if txt: return txt
        except:
            pass
    return fallback

def wait_engagement_widgets(driver, timeout=8):
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(0.5)
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: d.find_elements(By.CSS_SELECTOR, "span.u_cnt")
        )
    except:
        pass

LIKE_SELECTORS = ["span.u_likeit_text._count.num","em.u_cnt._count"]
COMMENT_SELECTORS = ["span.u_cnt._commentCount","span#commentCount"]

def _to_int(s):
    m = re.search(r"([\d,]+)", s or "")
    return int(m.group(1).replace(",", "")) if m else None

def get_int_by_selectors(driver, selectors):
    for css in selectors:
        for el in driver.find_elements(By.CSS_SELECTOR, css):
            v = _to_int(el.text)
            if v is not None: return v
    return None

def crawl_one(driver, row):
    info = {
        "platform": "blog",
        "administrative_dong": "신사동",

        "title": row.get("title",""),
        "link": row["link"],
        "bloggername": "",
        "bloggerlink": "",
        "postdate": "",
        "content_raw": "",
        "hashtags": "",
        "images": "",
        "videos": "",
        "like_count": None,
        "comment_count": None,
        "author_id": "",
        "post_id": "",
        "crawled_at": datetime.utcnow().replace(tzinfo=timezone.utc).isoformat().replace("+00:00","Z"),
        "status": "ok",
    }

    try:
        if not is_post_url(info["link"]):
            info["status"] = "skip"
            return info

        goto_post_view(driver, info["link"])

        aid, pid = extract_ids(driver.current_url)
        info["author_id"], info["post_id"] = aid, pid
        info["bloggerlink"] = f"https://blog.naver.com/{aid}"
        info["bloggername"] = extract_bloggername(driver, fallback=aid)

        raw = get_first_text(driver, ["span.se_publishDate","span#post_date"])
        m = re.search(r"(\d{4})\.(\d{1,2})\.(\d{1,2})", raw or "")
        if m:
            y, mo, d = map(int, m.groups())
            info["postdate"] = f"{y:04d}{mo:02d}{d:02d}"

        body, tags, imgs, vids = extract_body_tags_imgs_videos(driver)
        info["content_raw"] = body
        info["hashtags"] = "|".join(tags)
        info["images"]   = "|".join(imgs)
        info["videos"]   = "|".join(vids)

        wait_engagement_widgets(driver)

        info["like_count"] = get_int_by_selectors(driver, LIKE_SELECTORS)
        info["comment_count"] = get_int_by_selectors(driver, COMMENT_SELECTORS)

    except Exception as e:
        info["status"] = f"error:{type(e).__name__}"

    return info


# -----------------------------------
# 🔥 YEAR 전체(1~12월) 자동 실행
# -----------------------------------

def run_year():
    for month in range(1, 13):
        mm = f"{YEAR}{month:02d}"

        step1_path = os.path.join(STEP1_DIR, f"links_{QUERY}_{mm}.csv")
        step1_path = step1_path.replace(" ", "_")  # 공백 처리

        if not os.path.exists(step1_path):
            print(f"⚠️ Step1 결과 없음 → {step1_path}")
            continue

        print(f"\n========= 📌 {mm} 상세 크롤링 시작 =========")

        SAVE_PATH = os.path.join(STEP2_DIR, f"blog_posts_{QUERY}_{mm}.csv".replace(" ", "_"))

        df = pd.read_csv(step1_path)
        df.columns = [c.lower() for c in df.columns]
        df = df[df["link"].apply(is_post_url)]

        seeds = df.fillna("").to_dict(orient="records")

        driver = build_driver()
        out_rows = []

        try:
            for i, r in enumerate(seeds, 1):
                print(f"  [{i:03d}/{len(seeds):03d}] {r['link']}")
                out_rows.append(crawl_one(driver, r))
        finally:
            driver.quit()

        cols = [
            "platform","administrative_dong",
            "title","link","bloggername","bloggerlink","postdate",
            "content_raw","hashtags","images","videos",
            "like_count","comment_count","author_id","post_id",
            "crawled_at","status"
        ]

        pd.DataFrame(out_rows)[cols].to_csv(SAVE_PATH, index=False, encoding="utf-8-sig")

        print(f"✅ 저장 완료: {SAVE_PATH}")


if __name__ == "__main__":
    run_year()
