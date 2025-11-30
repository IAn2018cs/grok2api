#!/usr/bin/env python3
"""
数据迁移脚本 - 为现有token添加代理配置字段

此脚本会：
1. 读取 data/token.json 文件
2. 为每个token添加 proxy_url, cache_proxy_url, cf_clearance 字段（如果不存在）
3. 保存更新后的数据
4. 创建备份文件

注意：此脚本使用方案B - 现有token的新字段保持为空字符串，
使用全局代理作为fallback。不会将全局代理值复制到token中。
"""

import json
import shutil
from pathlib import Path
from datetime import datetime


def migrate_tokens():
    """执行token数据迁移"""
    # 文件路径
    token_file = Path(__file__).parent / "data" / "token.json"

    # 检查文件是否存在
    if not token_file.exists():
        print(f"❌ Token文件不存在: {token_file}")
        print("   如果这是首次运行，无需执行迁移。")
        return

    # 创建备份
    backup_file = token_file.parent / f"token.json.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    try:
        shutil.copy2(token_file, backup_file)
        print(f"✅ 已创建备份: {backup_file}")
    except Exception as e:
        print(f"❌ 创建备份失败: {e}")
        return

    # 读取现有数据
    try:
        with open(token_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"✅ 已读取token数据")
    except Exception as e:
        print(f"❌ 读取token文件失败: {e}")
        return

    # 需要添加的字段
    new_fields = {
        "proxy_url": "",
        "cache_proxy_url": "",
        "cf_clearance": ""
    }

    # 统计信息
    stats = {
        "ssoNormal": {"total": 0, "updated": 0},
        "ssoSuper": {"total": 0, "updated": 0}
    }

    # 遍历所有token并添加新字段
    for token_type in ["ssoNormal", "ssoSuper"]:
        if token_type not in data:
            continue

        for token, token_data in data[token_type].items():
            stats[token_type]["total"] += 1

            # 检查是否需要添加新字段
            fields_added = []
            for field, default_value in new_fields.items():
                if field not in token_data:
                    token_data[field] = default_value
                    fields_added.append(field)

            if fields_added:
                stats[token_type]["updated"] += 1

    # 保存更新后的数据
    try:
        with open(token_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"✅ 已保存更新后的数据")
    except Exception as e:
        print(f"❌ 保存数据失败: {e}")
        print(f"   可以从备份恢复: {backup_file}")
        return

    # 输出统计信息
    print("\n📊 迁移统计:")
    for token_type, stat in stats.items():
        type_name = "SSO Token" if token_type == "ssoNormal" else "SuperSSO Token"
        print(f"   {type_name}:")
        print(f"     - 总数: {stat['total']}")
        print(f"     - 已更新: {stat['updated']}")

    total_tokens = stats["ssoNormal"]["total"] + stats["ssoSuper"]["total"]
    total_updated = stats["ssoNormal"]["updated"] + stats["ssoSuper"]["updated"]

    print(f"\n✅ 迁移完成！")
    print(f"   共处理 {total_tokens} 个token，更新 {total_updated} 个")
    print(f"\n💡 说明:")
    print(f"   - 新添加的字段（proxy_url, cache_proxy_url, cf_clearance）默认为空")
    print(f"   - 系统会优先使用token级配置，如果为空则使用全局配置")
    print(f"   - 可以在管理界面为每个token单独设置代理配置")
    print(f"   - 备份文件: {backup_file}")


def migrate_mysql():
    """MySQL数据库迁移提示"""
    print("\n📌 MySQL数据库迁移:")
    print("   MySQL使用JSON字段存储token数据，无需手动迁移。")
    print("   代码已经通过 .get() 方法处理缺失字段，会自动返回空字符串。")
    print("   下次保存token时会自动添加新字段。")


if __name__ == "__main__":
    print("="*60)
    print("Token数据迁移脚本")
    print("="*60)
    print()

    # 执行JSON文件迁移
    migrate_tokens()

    # MySQL迁移提示
    migrate_mysql()

    print("\n" + "="*60)
