"""
扫描指定目录下所有 PDB 文件，统计氨基酸序列长度（CA 原子数），
按长度降序排列并导出到 Excel 文件。
"""

import os
from pathlib import Path
import sys

# ==================== 配置区域 ====================
PDB_DIR = "../data/PDB/PDB"          # PDB 文件夹相对路径
OUTPUT_FILE = "../data/PDB/pdb_lengths.xlsx"  # 输出 Excel 文件路径
MIN_LENGTH = 1500                    # 可调整筛选阈值（用于屏幕高亮）
# =================================================

def get_chain_length(pdb_path):
    """统计 PDB 文件中 CA 原子数量（即蛋白质链长度）"""
    try:
        with open(pdb_path, 'r', encoding='utf-8', errors='ignore') as f:
            ca_count = 0
            for line in f:
                if line.startswith("ATOM") and line[12:16].strip() == "CA":
                    ca_count += 1
            return ca_count
    except Exception:
        return 0

def save_to_excel(data, output_path):
    """将 (文件名, 长度) 列表保存为 Excel 文件"""
    try:
        from openpyxl import Workbook
    except ImportError:
        print("\n错误: 未找到 openpyxl 库。请先安装：pip install openpyxl")
        print("脚本将改为输出 CSV 文件。")
        csv_path = output_path.replace('.xlsx', '.csv')
        with open(csv_path, 'w', encoding='utf-8-sig') as f:
            f.write("文件名,长度\n")
            for name, length in data:
                f.write(f"{name},{length}\n")
        print(f"已保存为 CSV 文件: {os.path.abspath(csv_path)}")
        return

    wb = Workbook()
    ws = wb.active
    ws.title = "PDB Lengths"
    ws.append(["文件名", "长度"])
    for name, length in data:
        ws.append([name, length])
    wb.save(output_path)
    print(f"\nExcel 文件已保存: {os.path.abspath(output_path)}")

def main():
    print(f"正在检查目录: {Path(PDB_DIR).absolute()}", flush=True)
    pdb_dir = Path(PDB_DIR)
    if not pdb_dir.exists():
        print(f"目录不存在: {pdb_dir.absolute()}")
        return

    files = list(pdb_dir.glob("*.pdb")) + list(pdb_dir.glob("*.pdb1"))
    total = len(files)
    print(f"共找到 {total} 个 PDB 文件\n", flush=True)

    all_lengths = []   # 存储所有 (文件名, 长度)
    long_count = 0

    for idx, pdb_file in enumerate(files, 1):
        if idx % 100 == 0 or idx == 1:
            print(f"  扫描进度: {idx}/{total} ...", flush=True)

        length = get_chain_length(pdb_file)
        all_lengths.append((pdb_file.name, length))

        if length >= MIN_LENGTH:
            long_count += 1
            print(f"    -> 发现长结构: {pdb_file.name} (长度 {length})", flush=True)

    # 按长度降序排序
    all_lengths.sort(key=lambda x: x[1], reverse=True)

    print(f"\n扫描完成。共 {total} 个文件，其中 {long_count} 个长度 ≥ {MIN_LENGTH}。")

    # 导出到 Excel
    save_to_excel(all_lengths, OUTPUT_FILE)

    # 顺便在屏幕上打印前 20 个最长结构
    print("\n========== 长度排名前 20 ==========")
    for name, length in all_lengths[:20]:
        print(f"{name:<25s} 长度: {length}")

if __name__ == "__main__":
    main()