#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
zgzonre Excel 数据导入脚本
- 从 Excel 文件读取商品数据
- 图片同步到 OSS
- 入库 zgz_products_csv
- 支持指定 product_id 或全量导入
- 存在则更新（Upsert）
"""

import argparse
import time
import random
import string
import os
from datetime import datetime
from urllib.parse import urlparse
import requests
import pandas as pd
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

# 请求头（下载图片时使用）
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36',
    'Referer': 'https://www.zgzonre.com/',
    'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
}

# Excel 文件路径
EXCEL_FILE = '剩余分类需要导入的.xlsx'


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
    parsed = urlparse(original_url)
    path = parsed.path
    ext = path.split('.')[-1] if '.' in path else 'jpg'

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
            # 下载图片（带 Header）
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
                time.sleep(2)
            else:
                print(f"  [OSS ERROR] 上传最终失败 {image_url}")
                return None


def read_excel_data(product_id=None):
    """
    从 Excel 读取商品数据
    :param product_id: 指定商品ID，不传则获取全部
    :return: DataFrame
    """
    # 检查文件是否存在
    if not os.path.exists(EXCEL_FILE):
        print(f"[ERROR] Excel 文件不存在: {EXCEL_FILE}")
        return None

    df = pd.read_excel(EXCEL_FILE)

    # 重命名列，方便处理
    df = df.rename(columns={
        '产品ID': 'product_id',
        '产品编号': 'product_code',
        '商品名称': 'title',
        '产品图片': 'images',
        '商品详情': 'content_html',
        '分类名': 'category_path'
    })

    # 转换 product_id 为字符串
    df['product_id'] = df['product_id'].astype(str)

    if product_id:
        df = df[df['product_id'] == str(product_id)]

    return df


def upsert_product(conn, product_id, title, images, oss_image_url, content_html, category_path):
    """
    插入或更新商品详情
    :return: 'insert' | 'update' | None
    """
    with conn.cursor() as cursor:
        # 检查是否存在
        cursor.execute("SELECT id FROM zgz_products_csv WHERE product_id = %s AND category_path = %s", (product_id, category_path))
        exists = cursor.fetchone()

        if exists:
            # 更新
            sql = """
                UPDATE zgz_products_csv
                SET title = %s, images = %s, oss_image_url = %s, content_html = %s,
                    source_url = ''
                WHERE product_id = %s AND category_path = %s
            """
            cursor.execute(sql, (title, images, oss_image_url, content_html, product_id, category_path))
            conn.commit()
            return 'update'
        else:
            # 插入
            sql = """
                INSERT INTO zgz_products_csv (product_id, title, images, oss_image_url, content_html, category_path, source_url)
                VALUES (%s, %s, %s, %s, %s, %s, '')
            """
            cursor.execute(sql, (product_id, title, images, oss_image_url, content_html, category_path))
            conn.commit()
            return 'insert'


def check_data(conn):
    """数据自检"""
    df = pd.read_excel(EXCEL_FILE)
    excel_count = len(df)

    with conn.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM zgz_products_csv")
        db_count = cursor.fetchone()[0]

    print(f"\n=== 数据自检 ===")
    print(f"Excel 总数: {excel_count}")
    print(f"zgz_products_csv 总数: {db_count}")

    if excel_count == db_count:
        print("✓ 数量一致")
    else:
        print(f"✗ 数量不一致，差异: {excel_count - db_count}")


def main():
    parser = argparse.ArgumentParser(description='zgzonre Excel 数据导入脚本')
    parser.add_argument('--product_id', type=str, help='指定商品ID，不传则导入全部')
    parser.add_argument('--skip_oss', action='store_true', help='跳过 OSS 上传（仅导入数据）')
    args = parser.parse_args()

    conn = get_db_connection()
    print("数据库连接成功")

    # 初始化 OSS
    bucket = None
    if not args.skip_oss:
        bucket = get_oss_bucket()
        print("OSS 连接成功")

    # 读取 Excel 数据
    df = read_excel_data(args.product_id)
    if df is None:
        conn.close()
        return

    total = len(df)
    print(f"待导入商品数: {total}")

    if total == 0:
        print("没有需要导入的商品")
        conn.close()
        return

    # 统计
    insert_count = 0
    update_count = 0
    fail_count = 0

    for idx, row in df.iterrows():
        product_id = row['product_id']
        title = str(row['title']).strip().replace('\n', '').replace('\r', '') if pd.notna(row['title']) else ''
        images = str(row['images']).strip() if pd.notna(row['images']) else ''
        content_html = str(row['content_html']).strip().replace('\n', '').replace('\r', '') if pd.notna(row['content_html']) else ''
        category_path = str(row['category_path']).strip().replace('\n', '').replace('\r', '') if pd.notna(row['category_path']) else ''

        print(f"[{idx + 1}/{total}] 导入 product_id={product_id} ...")

        # 上传图片到 OSS
        oss_image_url = ''
        if bucket and images:
            image_list = [img.strip() for img in images.split('|') if img.strip()]
            print(f"  共 {len(image_list)} 张图片")

            oss_urls = []
            for img_url in image_list:
                print(f"  上传图片: {img_url}")
                oss_url = upload_image_to_oss(bucket, img_url)
                if oss_url:
                    oss_urls.append(oss_url)
                    print(f"  -> OSS: {oss_url}")
                time.sleep(0.3)  # 图片上传间隔

            oss_image_url = '|'.join(oss_urls)

        # 入库
        try:
            result = upsert_product(
                conn,
                product_id=product_id,
                title=title,
                images=images,
                oss_image_url=oss_image_url,
                content_html=content_html,
                category_path=category_path
            )

            if result == 'insert':
                insert_count += 1
                print(f"  -> 新增: {title}")
            elif result == 'update':
                update_count += 1
                print(f"  -> 更新: {title}")

        except Exception as e:
            fail_count += 1
            print(f"  [ERROR] 入库失败: {e}")

        time.sleep(0.2)  # 请求间隔

    print(f"\n=== 导入完成 ===")
    print(f"新增: {insert_count}, 更新: {update_count}, 失败: {fail_count}")

    # 数据自检
    check_data(conn)

    conn.close()


if __name__ == '__main__':
    main()
