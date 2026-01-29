#!/usr/bin/env python3
"""
按分辨率整理图片
将data目录下的图片按照分辨率分类到不同文件夹
"""
import os
from pathlib import Path
from PIL import Image
import shutil

def organize_images_by_resolution(source_dir='data'):
    """按分辨率整理图片"""
    source_path = Path(source_dir)

    if not source_path.exists():
        print(f"错误：目录 {source_dir} 不存在")
        return

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
            resolution_path = source_path / resolution_folder

            # 创建文件夹（如果不存在）
            resolution_path.mkdir(exist_ok=True)

            # 移动文件
            dest_path = resolution_path / file_path.name
            shutil.move(str(file_path), str(dest_path))

            # 统计
            processed += 1
            resolutions[resolution_folder] = resolutions.get(resolution_folder, 0) + 1

            print(f"✓ {file_path.name} ({width}x{height}) -> {resolution_folder}/")

        except Exception as e:
            errors += 1
            print(f"✗ 处理 {file_path.name} 时出错: {e}")

    # 输出统计信息
    print("\n" + "="*60)
    print("整理完成！")
    print(f"成功处理: {processed} 张图片")
    print(f"失败: {errors} 张")
    print(f"\n共创建 {len(resolutions)} 个分辨率文件夹:")
    for resolution, count in sorted(resolutions.items()):
        print(f"  {resolution}/ : {count} 张图片")

if __name__ == '__main__':
    organize_images_by_resolution()
