#!/usr/bin/env python3
"""
按分辨率整理图片
将指定目录下的图片按照分辨率分类到不同文件夹
"""
import os
import sys
import argparse
from pathlib import Path
from PIL import Image
import shutil
from datetime import datetime

def organize_images_by_resolution(source_dir=None):
    """按分辨率整理图片

    Args:
        source_dir: 源目录路径
            - 如果为 None：默认整理 data/{当前日期}/ 目录
            - 如果指定路径：整理指定目录
    """
    # 如果未指定目录，默认使用 data/{当前日期}/
    if source_dir is None:
        today = datetime.now().strftime('%Y%m%d')
        source_dir = f'data/{today}'

    source_path = Path(source_dir)

    if not source_path.exists():
        print(f"错误：目录 {source_dir} 不存在")
        return

    # 就地整理：将目录下的图片整理到 {分辨率}/ 子文件夹
    organize_single_directory(source_path)


def organize_single_directory(source_path):
    """整理单个目录的图片

    Args:
        source_path: 源目录（就地整理到该目录下的 {分辨率}/ 子文件夹）
    """
    target_base = source_path
    target_subdir = source_path.name
    print(f"整理模式：{source_path}/ -> {source_path}/{{分辨率}}/")

    # 统计信息
    processed = 0
    errors = 0
    resolutions = {}

    # 遍历所有图片文件
    for file_path in source_path.iterdir():
        # 跳过目录
        if file_path.is_dir():
            continue

        # 只处理图片文件
        if file_path.suffix.lower() not in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']:
            continue

        try:
            # 读取图片分辨率
            with Image.open(file_path) as img:
                width, height = img.size

            # 创建分辨率文件夹名称：宽度-高度
            resolution_folder = f"{width}-{height}"
            # 目标路径
            resolution_path = target_base / resolution_folder

            # 创建文件夹（如果不存在）
            resolution_path.mkdir(exist_ok=True)

            # 移动文件
            dest_path = resolution_path / file_path.name
            shutil.move(str(file_path), str(dest_path))

            # 统计
            processed += 1
            resolutions[resolution_folder] = resolutions.get(resolution_folder, 0) + 1

            print(f"✓ {file_path.name} ({width}x{height}) -> {target_subdir}/{resolution_folder}/")

        except Exception as e:
            errors += 1
            print(f"✗ 处理 {file_path.name} 时出错: {e}")

    # 输出统计信息
    print("\n" + "="*60)
    print("整理完成！")
    print(f"成功处理: {processed} 张图片")
    print(f"失败: {errors} 张")
    if resolutions:
        print(f"\n共创建 {len(resolutions)} 个分辨率文件夹:")
        for resolution, count in sorted(resolutions.items()):
            print(f"  {resolution}/ : {count} 张图片")
    print("\ndone")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='按分辨率整理图片到不同文件夹',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
使用示例：
  # 默认整理 data/{当前日期}/ 目录（例如：data/20260130/）
  python3 organize_by_resolution.py

  # 整理指定日期目录
  python3 organize_by_resolution.py --dir data/20260129

  # 整理任意目录
  python3 organize_by_resolution.py --dir ./images
        '''
    )
    parser.add_argument(
        '--dir',
        default=None,
        help='要整理的目录路径（默认：data/{当前日期}）'
    )

    args = parser.parse_args()
    organize_images_by_resolution(args.dir)
