# API Key 多密钥管理功能实现指南

## 功能概述

本项目已实现多 API Key 管理功能，支持：
- 自动生成 `sk-XXX` 格式的 API Key（48位长度）
- 为每个 API Key 设置备注、过期时间、IP 白名单
- 基于 IP 白名单的访问控制
- API Key 的启用/禁用/删除管理

## 后端实现（已完成）

### 1. 核心模块

#### API Key 管理器 (`app/services/api_key.py`)
- `APIKeyInfo`: API Key 数据模型
- `APIKeyManager`: API Key 管理器（单例模式）
- 主要方法：
  - `create_api_key()`: 创建新的 API Key
  - `delete_api_key()`: 删除 API Key
  - `update_api_key()`: 更新 API Key 信息
  - `verify_api_key()`: 验证 API Key（包含 IP 白名单检查）
  - `get_all_api_keys()`: 获取所有 API Key
  - `get_statistics()`: 获取统计信息

#### 认证模块 (`app/core/auth.py`)
- 支持多 API Key 验证
- 自动获取客户端 IP（支持 X-Forwarded-For、X-Real-IP）
- 向后兼容旧的单 API Key 模式

#### 存储模块 (`app/core/storage.py`)
- 支持文件、MySQL、Redis 三种存储方式
- API Key 数据存储在 `data/api_keys.json`
- MySQL 表：`grok_api_keys`
- Redis 键：`grok:api_keys`

### 2. 管理接口 (`app/api/admin/manage.py`)

所有接口都需要管理员会话认证（Bearer Token）。

#### GET `/api/api-keys`
获取所有 API Key 列表

**响应示例：**
```json
{
  "success": true,
  "data": [
    {
      "key": "sk-abcdefghijklmnopqrstuvwxyz1234567890ABCDE",
      "note": "生产环境密钥",
      "expire_time": 1735689600000,
      "ip_whitelist": ["192.168.1.100", "10.0.0.0/24"],
      "created_time": 1704067200000,
      "last_used_time": 1704153600000,
      "status": "active"
    }
  ],
  "total": 1
}
```

#### POST `/api/api-keys/create`
创建新的 API Key

**请求体：**
```json
{
  "note": "测试密钥",
  "expire_time": 1735689600000,  // 可选，毫秒时间戳，null 表示永不过期
  "ip_whitelist": ["192.168.1.100"]  // 可选，支持单个 IP 或 CIDR 格式
}
```

**响应示例：**
```json
{
  "success": true,
  "message": "API Key 创建成功",
  "data": {
    "key": "sk-newgeneratedkeyxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "note": "测试密钥",
    "expire_time": 1735689600000,
    "ip_whitelist": ["192.168.1.100"],
    "created_time": 1704067200000,
    "status": "active"
  }
}
```

#### PUT `/api/api-keys/update`
更新 API Key 信息

**请求体：**
```json
{
  "key": "sk-existingkeyxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "note": "更新后的备注",  // 可选
  "expire_time": 1735689600000,  // 可选
  "ip_whitelist": ["192.168.1.0/24"],  // 可选
  "status": "disabled"  // 可选：active, disabled, expired
}
```

#### DELETE `/api/api-keys/delete`
删除 API Key

**请求体：**
```json
{
  "key": "sk-keytobedeletedxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
}
```

#### GET `/api/api-keys/stats`
获取 API Key 统计信息

**响应示例：**
```json
{
  "success": true,
  "data": {
    "total": 10,
    "active": 8,
    "disabled": 1,
    "expired": 1
  }
}
```

## 前端 UI 实现指南

### 方案一：简单集成（推荐）

在 `admin.html` 中添加一个新的标签页用于 API Key 管理。

#### 步骤 1：添加导航标签

在现有的标签导航中添加 "API Key 管理" 标签：

```html
<!-- 在 Token 管理和系统配置之间添加 -->
<button class="tab-button" data-tab="apikeys">API Key 管理</button>
```

#### 步骤 2：添加 API Key 管理面板

```html
<!-- API Key 管理面板 -->
<div id="apikeys" class="tab-content" style="display: none;">
  <div class="section">
    <div class="section-header">
      <h2>API Key 管理</h2>
      <div class="stats">
        <span class="stat-item">总数: <span id="apikey-total">0</span></span>
        <span class="stat-item">活跃: <span id="apikey-active">0</span></span>
        <span class="stat-item">禁用: <span id="apikey-disabled">0</span></span>
        <span class="stat-item">过期: <span id="apikey-expired">0</span></span>
      </div>
    </div>

    <!-- 创建 API Key -->
    <div class="action-section">
      <h3>创建新的 API Key</h3>
      <div class="form-group">
        <label>备注：</label>
        <input type="text" id="new-apikey-note" placeholder="例如：生产环境密钥" />
      </div>
      <div class="form-group">
        <label>过期时间：</label>
        <input type="datetime-local" id="new-apikey-expire" />
        <label><input type="checkbox" id="never-expire" checked /> 永不过期</label>
      </div>
      <div class="form-group">
        <label>IP 白名单（每行一个）：</label>
        <textarea id="new-apikey-ips" rows="3" placeholder="例如：&#10;192.168.1.100&#10;10.0.0.0/24"></textarea>
      </div>
      <button onclick="createAPIKey()" class="btn-primary">生成 API Key</button>
    </div>

    <!-- API Key 列表 -->
    <div class="section-content">
      <h3>API Key 列表</h3>
      <table class="data-table">
        <thead>
          <tr>
            <th>API Key</th>
            <th>备注</th>
            <th>状态</th>
            <th>过期时间</th>
            <th>IP 白名单</th>
            <th>创建时间</th>
            <th>最后使用</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody id="apikey-list">
          <!-- 动态加载 -->
        </tbody>
      </table>
    </div>
  </div>
</div>
```

#### 步骤 3：添加 JavaScript 函数

```javascript
// API Key 管理函数
async function loadAPIKeys() {
    try {
        const response = await fetch('/api/api-keys', {
            headers: { 'Authorization': `Bearer ${sessionToken}` }
        });
        const data = await response.json();

        if (!data.success) {
            showMessage(data.message || '加载失败', 'error');
            return;
        }

        // 更新统计信息
        const stats = await fetchAPIKeyStats();
        document.getElementById('apikey-total').textContent = stats.total;
        document.getElementById('apikey-active').textContent = stats.active;
        document.getElementById('apikey-disabled').textContent = stats.disabled;
        document.getElementById('apikey-expired').textContent = stats.expired;

        // 渲染 API Key 列表
        const tbody = document.getElementById('apikey-list');
        tbody.innerHTML = '';

        data.data.forEach(apikey => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td><code>${apikey.key}</code></td>
                <td>${apikey.note || '-'}</td>
                <td><span class="status-${apikey.status}">${apikey.status}</span></td>
                <td>${apikey.expire_time ? new Date(apikey.expire_time).toLocaleString() : '永不过期'}</td>
                <td>${apikey.ip_whitelist.length > 0 ? apikey.ip_whitelist.join(', ') : '无限制'}</td>
                <td>${new Date(apikey.created_time).toLocaleString()}</td>
                <td>${apikey.last_used_time ? new Date(apikey.last_used_time).toLocaleString() : '从未使用'}</td>
                <td>
                    <button onclick="editAPIKey('${apikey.key}')">编辑</button>
                    <button onclick="deleteAPIKey('${apikey.key}')" class="btn-danger">删除</button>
                </td>
            `;
            tbody.appendChild(row);
        });
    } catch (error) {
        showMessage('加载 API Key 失败: ' + error.message, 'error');
    }
}

async function fetchAPIKeyStats() {
    const response = await fetch('/api/api-keys/stats', {
        headers: { 'Authorization': `Bearer ${sessionToken}` }
    });
    const data = await response.json();
    return data.data;
}

async function createAPIKey() {
    const note = document.getElementById('new-apikey-note').value;
    const neverExpire = document.getElementById('never-expire').checked;
    const expireInput = document.getElementById('new-apikey-expire').value;
    const ipsText = document.getElementById('new-apikey-ips').value;

    // 处理过期时间
    let expire_time = null;
    if (!neverExpire && expireInput) {
        expire_time = new Date(expireInput).getTime();
    }

    // 处理 IP 白名单
    const ip_whitelist = ipsText
        .split('\n')
        .map(ip => ip.trim())
        .filter(ip => ip.length > 0);

    try {
        const response = await fetch('/api/api-keys/create', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${sessionToken}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ note, expire_time, ip_whitelist })
        });

        const data = await response.json();

        if (data.success) {
            showMessage('API Key 创建成功！请妥善保管：' + data.data.key, 'success');
            // 清空表单
            document.getElementById('new-apikey-note').value = '';
            document.getElementById('new-apikey-expire').value = '';
            document.getElementById('new-apikey-ips').value = '';
            document.getElementById('never-expire').checked = true;
            // 重新加载列表
            loadAPIKeys();
        } else {
            showMessage(data.message || '创建失败', 'error');
        }
    } catch (error) {
        showMessage('创建 API Key 失败: ' + error.message, 'error');
    }
}

async function deleteAPIKey(key) {
    if (!confirm(`确定要删除此 API Key 吗？\n${key}`)) {
        return;
    }

    try {
        const response = await fetch('/api/api-keys/delete', {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${sessionToken}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ key })
        });

        const data = await response.json();

        if (data.success) {
            showMessage('API Key 删除成功', 'success');
            loadAPIKeys();
        } else {
            showMessage(data.message || '删除失败', 'error');
        }
    } catch (error) {
        showMessage('删除 API Key 失败: ' + error.message, 'error');
    }
}

async function editAPIKey(key) {
    // 这里可以实现一个编辑对话框
    const newNote = prompt('输入新的备注：');
    if (newNote === null) return;

    try {
        const response = await fetch('/api/api-keys/update', {
            method: 'PUT',
            headers: {
                'Authorization': `Bearer ${sessionToken}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ key, note: newNote })
        });

        const data = await response.json();

        if (data.success) {
            showMessage('API Key 更新成功', 'success');
            loadAPIKeys();
        } else {
            showMessage(data.message || '更新失败', 'error');
        }
    } catch (error) {
        showMessage('更新 API Key 失败: ' + error.message, 'error');
    }
}

// 在页面加载时调用
document.addEventListener('DOMContentLoaded', function() {
    // 在标签切换事件中添加
    document.querySelectorAll('.tab-button').forEach(button => {
        button.addEventListener('click', function() {
            const tabName = this.dataset.tab;
            if (tabName === 'apikeys') {
                loadAPIKeys();
            }
        });
    });
});
```

### 方案二：使用 API 测试工具（临时方案）

如果暂时不想修改前端，可以使用 curl 或 Postman 来管理 API Key：

#### 1. 登录获取会话 Token
```bash
curl -X POST http://localhost:8001/api/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}'
```

#### 2. 创建 API Key
```bash
SESSION_TOKEN="your_session_token_here"

curl -X POST http://localhost:8001/api/api-keys/create \
  -H "Authorization: Bearer $SESSION_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "note": "测试密钥",
    "expire_time": null,
    "ip_whitelist": ["192.168.1.100"]
  }'
```

#### 3. 查看所有 API Key
```bash
curl http://localhost:8001/api/api-keys \
  -H "Authorization: Bearer $SESSION_TOKEN"
```

#### 4. 更新 API Key
```bash
curl -X PUT http://localhost:8001/api/api-keys/update \
  -H "Authorization: Bearer $SESSION_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "key": "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "note": "更新后的备注",
    "status": "active"
  }'
```

#### 5. 删除 API Key
```bash
curl -X DELETE http://localhost:8001/api/api-keys/delete \
  -H "Authorization: Bearer $SESSION_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "key": "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
  }'
```

## 使用说明

### API Key 格式
- 格式：`sk-` + 45 个随机字符
- 总长度：48 个字符
- 示例：`sk-9aB3xYz7qWe5rTy1uI8oP4aSdF6gH2jK0lMnV3bCx9Z`

### IP 白名单格式
支持两种格式：
1. 单个 IP：`192.168.1.100`
2. IP 段（CIDR）：`10.0.0.0/24`

### 过期时间
- 毫秒级时间戳（JavaScript: `Date.getTime()`）
- 设置为 `null` 表示永不过期
- 过期后 API Key 自动标记为 `expired` 状态

### 状态说明
- `active`: 正常可用
- `disabled`: 已禁用
- `expired`: 已过期

## 安全建议

1. **定期轮换 API Key**：建议每 3-6 个月更换一次生产环境密钥
2. **使用 IP 白名单**：限制只有特定 IP 可以访问
3. **设置过期时间**：为临时密钥设置合理的过期时间
4. **妥善保管密钥**：创建后立即复制保存，系统不会明文存储
5. **最小权限原则**：为不同环境创建不同的密钥
6. **监控使用情况**：定期检查 `last_used_time` 字段，删除长期未使用的密钥

## 测试步骤

1. 启动应用：`python3 main.py` 或 `uvicorn main:app --reload`
2. 登录管理后台：访问 http://localhost:8001/login
3. 使用 curl 或前端 UI 创建一个测试 API Key
4. 使用新创建的 API Key 调用 API 接口测试
5. 测试 IP 白名单限制（如果设置了）
6. 测试过期功能（创建一个已过期的密钥）

## 故障排查

### 问题：API Key 验证失败
- 检查 `data/api_keys.json` 文件是否存在且格式正确
- 查看日志确认 API Key 管理器是否正确初始化
- 确认客户端请求头包含正确的 `Authorization: Bearer <api_key>`

### 问题：IP 白名单不生效
- 检查反向代理配置，确保正确传递 `X-Forwarded-For` 或 `X-Real-IP` 头
- 查看日志中的客户端 IP 是否正确识别
- 验证 IP 白名单格式（单个 IP 或 CIDR）

### 问题：存储失败
- 检查 `data` 目录的写入权限
- 如果使用 MySQL/Redis，确认连接配置正确
- 查看日志中的详细错误信息

## 数据迁移

### 从旧的单 API Key 迁移

如果之前在 `setting.toml` 中配置了单个 `api_key`，可以通过以下步骤迁移：

```python
# 迁移脚本示例
import asyncio
from app.core.storage import storage_manager
from app.services.api_key import api_key_manager
from app.core.config import setting

async def migrate_old_api_key():
    await storage_manager.init()
    storage = storage_manager.get_storage()
    api_key_manager.set_storage(storage)
    await api_key_manager._load_data()

    old_key = setting.grok_config.get("api_key")
    if old_key:
        # 创建新的 API Key（手动设置 key 值）
        api_key_info = await api_key_manager.create_api_key(
            note="从旧配置迁移",
            expire_time=None,
            ip_whitelist=[]
        )
        print(f"已创建新 API Key: {api_key_info.key}")
        print("请更新 setting.toml，移除旧的 api_key 配置")

if __name__ == "__main__":
    asyncio.run(migrate_old_api_key())
```

## 后续优化建议

1. **前端 UI 完善**：
   - 添加批量导入/导出功能
   - 实现 API Key 的使用统计图表
   - 添加更详细的编辑对话框

2. **功能增强**：
   - 支持 API Key 的使用频率限制
   - 添加 API Key 的权限范围控制
   - 实现 API Key 的使用日志记录

3. **安全加固**：
   - 存储 API Key 的哈希值而非明文
   - 添加 API Key 的访问日志审计
   - 实现异常访问告警机制

## 总结

多 API Key 管理功能已经在后端完全实现，包括：
- ✅ 核心管理器和数据模型
- ✅ 完整的 REST API 接口
- ✅ 存储层支持（文件/MySQL/Redis）
- ✅ 认证和 IP 白名单验证
- ✅ 应用启动初始化

前端 UI 可以根据上述指南进行集成，或者直接使用 API 接口管理。
