"""
数据迁移脚本
从 backend/mcp-lessons 迁移数据到 MemGraph
"""
import shutil
from pathlib import Path

SOURCE_DIR = Path(r"D:\work\AIGenTest\backend\mcp-lessons\records")
TARGET_DIR = Path(r"D:\work\AIGenTest\MemGraph\records")

def migrate():
    """迁移数据"""
    if not SOURCE_DIR.exists():
        print(f"Source directory not found: {SOURCE_DIR}")
        return

    # 创建目标目录
    TARGET_DIR.mkdir(parents=True, exist_ok=True)

    # 复制文件
    print(f"Migrating from {SOURCE_DIR} to {TARGET_DIR}")

    count = 0
    for src_file in SOURCE_DIR.rglob("*.md"):
        # 计算相对路径
        relative_path = src_file.relative_to(SOURCE_DIR)
        target_file = TARGET_DIR / relative_path

        # 创建目标目录
        target_file.parent.mkdir(parents=True, exist_ok=True)

        # 复制文件
        shutil.copy2(src_file, target_file)
        count += 1
        print(f"  Copied: {relative_path}")

    print(f"\nMigration complete: {count} files copied")

if __name__ == "__main__":
    migrate()
