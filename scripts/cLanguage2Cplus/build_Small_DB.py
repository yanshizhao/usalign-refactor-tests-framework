"""
Windows 环境下从 I-TASSER 模板库随机抽取 PDB 文件构建 smallDB
用法：
    1. 将本脚本放在 scripts/cLanguage2Cplus/ 目录下
    2. 修改下方 SOURCE_DIR 为您的 I-TASSER 库解压路径
    3. 在命令行执行: python build_Small_DB.py
"""

import os
import random
import shutil
import sys

# ==================== 配置区域 ====================
# 请修改为您的 I‑TASSER 库实际解压路径（包含大量 .pdb 文件的目录）
SOURCE_DIR = r"D:\qlab\us-align_modify\tests\data\PDB\PDB"

# 目标目录由脚本自动推断，无需修改
NUM_STRUCTURES = 100
# =================================================


def main():
    # 1. 自动确定 cLanguage2Cplus 测试目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    target_dir = os.path.join(script_dir, "data", "smallDB")

    print(f"脚本位置: {script_dir}")
    print(f"目标目录: {target_dir}")

    # 2. 检查源目录
    if not os.path.isdir(SOURCE_DIR):
        print(f"错误: 源目录不存在: {SOURCE_DIR}")
        print("请修改脚本中的 SOURCE_DIR 为 I-TASSER 库的实际解压路径。")
        return 1

    # 3. 清空并创建目标目录（每次运行前先清空 smallDB 内所有内容）
    if os.path.exists(target_dir):
        try:
            shutil.rmtree(target_dir)
            print(f"已清空原有目录: {target_dir}")
        except Exception as e:
            print(f"错误: 无法清空目标目录 {target_dir} - {e}")
            return 1
    os.makedirs(target_dir, exist_ok=True)
    print(f"目标目录已就绪: {target_dir}")

    # 4. 获取源目录中的所有 PDB 文件
    pdb_files = [f for f in os.listdir(SOURCE_DIR) if f.lower().endswith('.pdb')]
    print(f"源目录中共找到 {len(pdb_files)} 个 PDB 文件。")

    if len(pdb_files) == 0:
        print("错误: 源目录中没有任何 .pdb 文件，请检查路径。")
        return 1

    # 5. 随机抽取（若不足设定数量则全选）
    random.seed(42)   # 固定种子，保证可重复性
    if len(pdb_files) >= NUM_STRUCTURES:
        selected_files = random.sample(pdb_files, NUM_STRUCTURES)
    else:
        selected_files = pdb_files
        print(f"警告: 源目录文件数少于 {NUM_STRUCTURES}，将全部复制。")

    # 6. 复制文件
    success = 0
    for f in selected_files:
        src = os.path.join(SOURCE_DIR, f)
        dst = os.path.join(target_dir, f)
        try:
            shutil.copy2(src, dst)   # copy2 保留原文件时间戳等信息
            success += 1
        except Exception as e:
            print(f"复制失败: {f} - {e}")

    print(f"已成功复制 {success} 个 PDB 文件到目标目录。")

    # 7. 生成 list 文件（每行一个 PDB ID，不含扩展名）
    list_path = os.path.join(target_dir, "list.txt")
    with open(list_path, "w", encoding="utf-8") as f:
        for pdb_file in selected_files:
            pdb_id = os.path.splitext(pdb_file)[0]   # 去掉 .pdb
            f.write(pdb_id + "\n")
    print(f"list.txt 文件已生成: {list_path}")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n用户中断操作")
        sys.exit(1)
    except Exception as e:
        print(f"程序异常: {e}")
        sys.exit(1)