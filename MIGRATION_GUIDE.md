# Token级代理配置 - 迁移指南

## 📋 概述

本次更新将全局代理设置改为支持**Token级别的独立代理配置**。每个Token现在可以配置自己的：
- **Proxy URL** (服务代理)
- **Cache Proxy URL** (缓存代理)
- **CF Clearance**

## ✨ 主要变更

### 1. Token数据结构变更

每个Token现在包含以下新字段：

```json
{
  "token_value": {
    "createdTime": 1234567890000,
    "remainingQueries": -1,
    "status": "active",
    "tags": [],
    "note": "",
    "proxy_url": "",           // 新增：服务代理
    "cache_proxy_url": "",     // 新增：缓存代理
    "cf_clearance": ""         // 新增：CF Clearance
  }
}
```

### 2. 配置优先级

系统按以下优先级使用配置：

1. **Token级配置** - 如果Token设置了代理，优先使用
2. **全局配置** - 如果Token未设置代理，则使用全局配置

这种设计保证了向后兼容性，现有配置无需修改即可继续工作。

## 🔄 数据迁移

### 自动迁移

运行迁移脚本：

```bash
python migrate_token_fields.py
```

脚本会：
- ✅ 自动备份现有的 `data/token.json`
- ✅ 为所有Token添加新字段（默认为空字符串）
- ✅ 保持现有数据不变
- ✅ 输出详细的迁移统计

### MySQL数据库

**无需手动迁移！**

- MySQL使用JSON字段存储数据，代码已处理缺失字段
- 下次保存Token时会自动添加新字段
- 现有Token读取时会自动返回空字符串（fallback到全局配置）

## 🎯 使用方法

### 添加Token时配置代理

在管理界面添加Token时，可以为所有Token配置相同的代理：

1. 点击"添加Token"按钮
2. 输入Token列表（每行一个）
3. **可选**：填写代理配置
   - **Proxy URL**: 例如 `socks5://127.0.0.1:7890`
   - **Cache Proxy URL**: 例如 `socks5://127.0.0.1:7890`
   - **CF Clearance**: 例如 `0.123456789.1234567890.abcdef...`
4. 点击"添加"

> 💡 **提示**：如果不填写，Token将使用全局代理配置

### 编辑现有Token的代理配置

1. 在Token列表中找到要配置的Token
2. 点击"编辑信息"按钮
3. 在弹出的对话框中设置：
   - 标签和备注
   - **Proxy URL** (服务代理)
   - **Cache Proxy URL** (缓存代理)
   - **CF Clearance**
4. 点击"保存"

## 🌟 使用场景

### 场景1：不同Token使用不同代理

适合需要分散IP的场景：

```
Token A: proxy_url = socks5://proxy1.example.com:1080
Token B: proxy_url = socks5://proxy2.example.com:1080
Token C: proxy_url = socks5://proxy3.example.com:1080
```

### 场景2：部分Token使用代理，部分直连

适合混合环境：

```
Token A: proxy_url = socks5://127.0.0.1:7890  (使用代理)
Token B: proxy_url = ""                        (直连，使用全局配置)
Token C: proxy_url = ""                        (直连，使用全局配置)
```

### 场景3：不同Token使用不同CF Clearance

适合多账号管理：

```
Token A: cf_clearance = "cf_clearance_value_1"
Token B: cf_clearance = "cf_clearance_value_2"
Token C: cf_clearance = ""  (使用全局CF Clearance)
```

## 🔧 技术细节

### API变更

#### 1. 添加Token API

**请求**：`POST /api/tokens/add`

```json
{
  "tokens": ["token1", "token2"],
  "token_type": "sso",
  "proxy_url": "socks5://127.0.0.1:7890",      // 新增，可选
  "cache_proxy_url": "socks5://127.0.0.1:7890", // 新增，可选
  "cf_clearance": "cf_value"                    // 新增，可选
}
```

#### 2. 更新代理配置API

**请求**：`POST /api/tokens/proxy`

```json
{
  "token": "token_value",
  "token_type": "sso",
  "proxy_url": "socks5://127.0.0.1:7890",
  "cache_proxy_url": "socks5://127.0.0.1:7890",
  "cf_clearance": "cf_value"
}
```

#### 3. Token列表API

**响应**：`GET /api/tokens`

```json
{
  "success": true,
  "data": [
    {
      "token": "token_value",
      "token_type": "sso",
      "proxy_url": "",              // 新增
      "cache_proxy_url": "",        // 新增
      "cf_clearance": ""            // 新增
      ...
    }
  ]
}
```

### 代码变更

#### Token管理器 (token.py)

```python
# 新增方法
def get_token_config(auth_token: str) -> Dict[str, str]:
    """获取Token的配置（代理、CF Clearance等）"""
    # 返回 {"proxy_url": "", "cache_proxy_url": "", "cf_clearance": ""}

async def update_token_proxy(...):
    """更新Token代理配置"""
```

#### 客户端 (client.py)

```python
# 使用Token级配置
token_config = token_manager.get_token_config(token)
cf = token_config.get("cf_clearance", "") or global_cf
proxy = token_config.get("proxy_url", "") or global_proxy
```

## ⚠️ 注意事项

1. **向后兼容**：现有系统无需修改配置即可正常运行
2. **可选配置**：所有Token级配置都是可选的
3. **Fallback机制**：Token级配置为空时自动使用全局配置
4. **数据备份**：迁移脚本会自动创建备份文件

## 🐛 故障排查

### Token无法连接？

1. 检查Token级代理配置是否正确
2. 检查全局代理配置是否正确
3. 查看日志确认使用了哪个代理
4. 尝试清空Token级配置，使用全局配置

### 迁移脚本报错？

1. 确认 `data/token.json` 文件存在
2. 确认有读写权限
3. 查看备份文件是否已创建
4. 从备份恢复后重试

## 📝 更新日志

### v2.0.0 (2025-01-XX)

**新功能**：
- ✨ 支持Token级别的代理配置
- ✨ 支持Token级别的CF Clearance配置
- ✨ 管理界面支持添加/编辑Token代理
- ✨ 配置优先级：Token级 > 全局级

**改进**：
- 🔧 优化代理配置逻辑
- 🔧 改进错误处理
- 📚 完善文档和迁移指南

**向后兼容**：
- ✅ 现有配置无需修改
- ✅ 现有Token自动兼容
- ✅ 支持渐进式迁移

---

**如有问题，请提交Issue或查看项目文档。**
