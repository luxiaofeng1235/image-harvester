#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
zgzonre 产品采集脚本
- 从 zgz_products_cate 读取商品列表
- 抓取详情页并入库 zgz_products
- 支持指定 goods_id 或全量采集
- 存在则更新（Upsert）
- 图片同步到 OSS
"""

import argparse
import time
import random
import string
from datetime import datetime
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
import pymysql
import oss2

# 数据库配置
DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': '*',
    'password': '*',
    'database': 'jiujie_shop',
    'charset': 'utf8mb4'
}

# OSS 配置
OSS_CONFIG = {
    'access_key_id': '*',
    'access_key_secret': '*',
    'endpoint': 'oss-cn-shanghai.aliyuncs.com',
    'bucket': 'static-nine-world',
    'view_domain': 'https://static.jsss999.com/'
}

# 请求头
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36',
    'Referer': 'https://www.zgzonre.com/'
}


def get_db_connection():
    """获取数据库连接"""
    return pymysql.connect(**DB_CONFIG)


def get_oss_bucket():
    """获取 OSS Bucket 实例"""
    auth = oss2.Auth(OSS_CONFIG['access_key_id'], OSS_CONFIG['access_key_secret'])
    return oss2.Bucket(auth, OSS_CONFIG['endpoint'], OSS_CONFIG['bucket'])


def generate_oss_filename(original_url):
    """
    生成 OSS 文件名
    格式：uploads/files/时间戳+随机字符.后缀
    """
    # 获取原文件后缀
    parsed = urlparse(original_url)
    path = parsed.path
    ext = path.split('.')[-1] if '.' in path else 'jpg'

    # 生成时间戳 + 随机字符
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))

    filename = f"uploads/files/{timestamp}{random_str}.{ext}"
    return filename


def upload_image_to_oss(bucket, image_url, max_retries=3):
    """
    下载图片并上传到 OSS（带重试机制）
    :param bucket: OSS Bucket 实例
    :param image_url: 原图 URL
    :param max_retries: 最大重试次数
    :return: OSS URL 或 None
    """
    for attempt in range(1, max_retries + 1):
        try:
            # 下载图片
            resp = requests.get(image_url, headers=HEADERS, timeout=30)
            resp.raise_for_status()

            # 生成 OSS 文件名
            oss_key = generate_oss_filename(image_url)

            # 上传到 OSS
            bucket.put_object(oss_key, resp.content)

            # 生成访问 URL
            oss_url = OSS_CONFIG['view_domain'].rstrip('/') + '/' + oss_key
            return oss_url

        except Exception as e:
            print(f"  [OSS RETRY {attempt}/{max_retries}] 上传失败 {image_url}: {e}")
            if attempt < max_retries:
                time.sleep(2)  # 重试前等待2秒
            else:
                print(f"  [OSS ERROR] 上传最终失败 {image_url}")
                return None


def get_products_from_cate(conn, goods_id=None, category_path=None):
    """
    从 zgz_products_cate 获取商品列表
    :param conn: 数据库连接
    :param goods_id: 指定商品ID，不传则获取全部
    :param category_path: 指定分类，不传则获取全部
    :return: 商品列表 [(goods_id, source_url, category_path), ...]
    """
    with conn.cursor() as cursor:
        if goods_id:
            sql = "SELECT goods_id, source_url, category_path FROM zgz_products_cate WHERE goods_id = %s"
            cursor.execute(sql, (goods_id,))
        elif category_path:
            sql = "SELECT goods_id, source_url, category_path FROM zgz_products_cate WHERE category_path = %s"
            cursor.execute(sql, (category_path,))
        else:
            sql = "SELECT goods_id, source_url, category_path FROM zgz_products_cate"
            cursor.execute(sql)
        return cursor.fetchall()


def fetch_product_detail(url, max_retries=3):
    """
    抓取商品详情页（带重试机制）
    :param url: 详情页URL
    :param max_retries: 最大重试次数
    :return: dict {title, images, content_html} 或 None
    """
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'lxml')

            # 1. 提取标题
            title_tag = soup.find('title')
            title = title_tag.text.strip() if title_tag else ''

            # 2. 提取图片
            # 优先缩略图列表，否则用主图
            thumbs = soup.select('.wp-new-prodcuts-detail-picture-small-element img')
            if thumbs:
                images = [img.get('src') for img in thumbs if img.get('src')]
            else:
                main_img = soup.select_one('.wp-tb_product_detail-imgpreview')
                images = [main_img.get('src')] if main_img and main_img.get('src') else []

            # 去重并拼接
            images = list(dict.fromkeys(images)) #保持顺序去重
            images_str = '|'.join(images)

            # 3. 提取详情HTML
            content_html = ''
            for selector in ['.artview_detail', '.goods-info', '.desckey0']:
                el = soup.select_one(selector)
                if el:
                    content_html = str(el)
                    break

            # 清理换行符，避免导出CSV时错位
            content_html = content_html.replace('\n', '').replace('\r', '')
            title = title.replace('\n', '').replace('\r', '')

            return {
                'title': title,
                'images': images_str,
                'images_list': images,  # 保留列表用于 OSS 上传
                'content_html': content_html
            }

        except Exception as e:
            print(f"  [RETRY {attempt}/{max_retries}] 抓取失败 {url}: {e}")
            if attempt < max_retries:
                time.sleep(2)  # 重试前等待2秒
            else:
                print(f"[ERROR] 抓取最终失败 {url}")
                return None


def upsert_product(conn, product_id, title, images, oss_image_url, content_html, category_path, source_url):
    """
    插入或更新商品详情
    :return: 'insert' | 'update' | None
    """
    with conn.cursor() as cursor:
        # 检查是否存在
        cursor.execute("SELECT id FROM zgz_products WHERE product_id = %s AND category_path = %s", (product_id, category_path))
        exists = cursor.fetchone()

        if exists:
            # 更新
            sql = """
                UPDATE zgz_products
                SET title = %s, images = %s, oss_image_url = %s, content_html = %s,
                    source_url = %s
                WHERE product_id = %s AND category_path = %s
            """
            cursor.execute(sql, (title, images, oss_image_url, content_html, source_url, product_id, category_path))
            conn.commit()
            return 'update'
        else:
            # 插入
            sql = """
                INSERT INTO zgz_products (product_id, title, images, oss_image_url, content_html, category_path, source_url)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(sql, (product_id, title, images, oss_image_url, content_html, category_path, source_url))
            conn.commit()
            return 'insert'


def check_data(conn):
    """数据自检"""
    with conn.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM zgz_products_cate")
        cate_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM zgz_products")
        product_count = cursor.fetchone()[0]

        print(f"\n=== 数据自检 ===")
        print(f"zgz_products_cate 总数: {cate_count}")
        print(f"zgz_products 总数: {product_count}")

        if cate_count == product_count:
            print("✓ 数量一致")
        else:
            print(f"✗ 数量不一致，差异: {cate_count - product_count}")


def main():
    parser = argparse.ArgumentParser(description='zgzonre 产品采集脚本')
    parser.add_argument('--goods_id', type=str, help='指定商品ID，不传则采集全部')
    parser.add_argument('--category', type=str, help='指定分类，如：加热器->导热油加热器')
    args = parser.parse_args()

    conn = get_db_connection()
    print("数据库连接成功")

    # 初始化 OSS
    bucket = get_oss_bucket()
    print("OSS 连接成功")

    # 获取商品列表
    products = get_products_from_cate(conn, args.goods_id, args.category)
    total = len(products)
    print(f"待采集商品数: {total}")

    if total == 0:
        print("没有需要采集的商品")
        conn.close()
        return

    # 统计
    insert_count = 0
    update_count = 0
    fail_count = 0

    for idx, (goods_id, source_url, category_path) in enumerate(products, 1):
        print(f"[{idx}/{total}] 采集 goods_id={goods_id} ...")

        detail = fetch_product_detail(source_url)
        if not detail:
            fail_count += 1
            continue

        # 上传图片到 OSS
        img_count = len(detail['images_list'])
        print(f"  采集到 {img_count} 张图片")
        oss_urls = []
        for img_url in detail['images_list']:
            print(f"  上传图片: {img_url}")
            oss_url = upload_image_to_oss(bucket, img_url)
            if oss_url:
                oss_urls.append(oss_url)
                print(f"  -> OSS: {oss_url}")

        oss_image_url = '|'.join(oss_urls)

        result = upsert_product(
            conn,
            product_id=goods_id,
            title=detail['title'],
            images=detail['images'],
            oss_image_url=oss_image_url,
            content_html=detail['content_html'],
            category_path=category_path,
            source_url=source_url
        )

        if result == 'insert':
            insert_count += 1
            print(f"  -> 新增: {detail['title']}")
        elif result == 'update':
            update_count += 1
            print(f"  -> 更新: {detail['title']}")

        # 请求间隔，避免过快
        time.sleep(0.5)

    print(f"\n=== 采集完成 ===")
    print(f"新增: {insert_count}, 更新: {update_count}, 失败: {fail_count}")

    # 数据自检
    check_data(conn)

    conn.close()


if __name__ == '__main__':
    main()
