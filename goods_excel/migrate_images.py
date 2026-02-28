"""
将 jj_wangyi_goods 表中的外链图片迁移到阿里云 OSS
多线程并发下载+上传
"""
import re
import os
import time
import hashlib
import requests
import pymysql
import oss2
import urllib3
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

urllib3.disable_warnings()

# ── 配置 ──
DB_CONFIG = {
    "host": "localhost",
    "user": "*",
    "password": "*",
    "database": "jiujie_shop",
    "charset": "utf8mb4",
}

OSS_ACCESS_KEY_ID = "*"
OSS_ACCESS_KEY_SECRET = "*"
OSS_BUCKET = "static-nine-world"
OSS_ENDPOINT = "oss-cn-shanghai.aliyuncs.com"
OSS_VIEW_DOMAIN = "https://static.jsss999.com/"
OSS_PREFIX = "goods/images/"
WORKERS = 20  # 并发线程数

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

auth = oss2.Auth(OSS_ACCESS_KEY_ID, OSS_ACCESS_KEY_SECRET)
bucket = oss2.Bucket(auth, OSS_ENDPOINT, OSS_BUCKET)


def url_to_oss_key(url: str) -> str:
    md5 = hashlib.md5(url.encode()).hexdigest()
    path = urlparse(url).path
    ext = os.path.splitext(path)[1].lower().split('?')[0]
    if ext not in ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'):
        ext = '.jpg'
    return f"{OSS_PREFIX}{md5}{ext}"


CONTENT_TYPE_MAP = {
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.png': 'image/png',
    '.gif': 'image/gif',
    '.webp': 'image/webp',
    '.bmp': 'image/bmp',
}


def process_one(url: str) -> tuple:
    """下载一张图并上传到OSS，返回 (原URL, 新URL 或 None)"""
    oss_key = url_to_oss_key(url)
    try:
        resp = requests.get(url, headers={"User-Agent": UA}, timeout=15, verify=False)
        if resp.status_code == 200 and len(resp.content) > 100:
            ext = os.path.splitext(oss_key)[1].lower()
            content_type = CONTENT_TYPE_MAP.get(ext, 'image/jpeg')
            bucket.put_object(oss_key, resp.content, headers={"Content-Type": content_type})
            return (url, f"{OSS_VIEW_DOMAIN}{oss_key}")
    except Exception:
        pass
    return (url, None)


def extract_img_urls(html: str) -> list:
    return re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', html, re.IGNORECASE)


def main():
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT id, image, description FROM jj_wangyi_goods")
    rows = cursor.fetchall()
    print(f"共 {len(rows)} 条记录")

    # Step 1: 收集去重
    print("\n[1/3] 收集图片URL...")
    all_urls = set()
    for row in rows:
        if row["image"]:
            all_urls.add(row["image"].strip())
        if row["description"]:
            for u in extract_img_urls(row["description"]):
                all_urls.add(u.strip())
    url_list = list(all_urls)
    print(f"  去重后 {len(url_list)} 个")

    # Step 2: 多线程下载+上传
    print(f"\n[2/3] 并发下载上传 ({WORKERS}线程)...")
    success_map = {}
    failed = 0
    done = 0

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(process_one, u): u for u in url_list}
        for future in as_completed(futures):
            done += 1
            url, new_url = future.result()
            if new_url:
                success_map[url] = new_url
            else:
                failed += 1
            if done % 500 == 0:
                print(f"  进度: {done}/{len(url_list)} 成功{len(success_map)} 失败{failed}")

    print(f"  完成: 成功 {len(success_map)}, 失败 {failed}")

    # Step 3: 更新数据库
    print("\n[3/3] 更新数据库...")
    updated = 0
    for row in rows:
        new_image = row["image"]
        new_desc = row["description"] or ""
        changed = False

        if row["image"] and row["image"].strip() in success_map:
            new_image = success_map[row["image"].strip()]
            changed = True

        for old_url, new_url in success_map.items():
            if old_url in new_desc:
                new_desc = new_desc.replace(old_url, new_url)
                changed = True

        if changed:
            cursor.execute(
                "UPDATE jj_wangyi_goods SET image=%s, description=%s, update_time=%s WHERE id=%s",
                (new_image, new_desc, int(time.time()), row["id"])
            )
            updated += 1

    conn.commit()
    cursor.close()
    conn.close()
    print(f"  更新 {updated} 条记录")
    print(f"\n全部完成!")


if __name__ == "__main__":
    main()
