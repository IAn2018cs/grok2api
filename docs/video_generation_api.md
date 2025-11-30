# 视频生成 API 文档

## 概述

视频生成API允许你通过提供一张图片和文本提示词来生成视频内容。该接口基于 Grok Imagine 0.9 模型，支持将静态图片转换为动态视频。

**基础URL**: `http://your-server:port`
**接口路径**: `/v1/videos/generations`
**请求方法**: `POST`
**认证方式**: Bearer Token（通过 Authorization 头或 API Key）

---

## 接口详情

### 请求 URL

```
POST /v1/videos/generations
```

### 请求头（Headers）

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| Authorization | string | 是 | Bearer Token，格式：`Bearer YOUR_API_KEY` |
| Content-Type | string | 是 | 必须为 `application/json` |

### 请求参数（Body）

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| image_url | string | 是 | - | 输入图片的URL，支持http/https链接或base64格式 |
| prompt | string | 是 | - | 视频生成提示词，描述你希望生成的视频效果 |
| model | string | 否 | grok-imagine-0.9 | 使用的视频生成模型 |

#### image_url 支持格式

1. **HTTP/HTTPS URL**:
   ```
   https://example.com/image.jpg
   http://example.com/image.png
   ```

2. **Base64 编码**:
   ```
   data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAA...
   data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAA...
   ```

### 请求示例

#### cURL

```bash
curl -X POST 'http://localhost:8001/v1/videos/generations' \
  -H 'Authorization: Bearer YOUR_API_KEY' \
  -H 'Content-Type: application/json' \
  -d '{
    "image_url": "https://example.com/my-image.jpg",
    "prompt": "让图片中的人物挥手微笑，背景有轻微的摇曳",
    "model": "grok-imagine-0.9"
  }'
```

#### Python

```python
import requests
import json

url = "http://localhost:8001/v1/videos/generations"
headers = {
    "Authorization": "Bearer YOUR_API_KEY",
    "Content-Type": "application/json"
}
data = {
    "image_url": "https://example.com/my-image.jpg",
    "prompt": "让图片中的人物挥手微笑，背景有轻微的摇曳",
    "model": "grok-imagine-0.9"
}

response = requests.post(url, headers=headers, json=data)
result = response.json()
print(f"视频URL: {result['video_url']}")
```

#### JavaScript (Node.js)

```javascript
const axios = require('axios');

const url = 'http://localhost:8001/v1/videos/generations';
const headers = {
  'Authorization': 'Bearer YOUR_API_KEY',
  'Content-Type': 'application/json'
};
const data = {
  image_url: 'https://example.com/my-image.jpg',
  prompt: '让图片中的人物挥手微笑，背景有轻微的摇曳',
  model: 'grok-imagine-0.9'
};

axios.post(url, data, { headers })
  .then(response => {
    console.log('视频URL:', response.data.video_url);
  })
  .catch(error => {
    console.error('错误:', error.response.data);
  });
```

#### JavaScript (Fetch)

```javascript
fetch('http://localhost:8001/v1/videos/generations', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer YOUR_API_KEY',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    image_url: 'https://example.com/my-image.jpg',
    prompt: '让图片中的人物挥手微笑，背景有轻微的摇曳',
    model: 'grok-imagine-0.9'
  })
})
.then(response => response.json())
.then(data => {
  console.log('视频URL:', data.video_url);
})
.catch(error => {
  console.error('错误:', error);
});
```

---

## 响应格式

### 成功响应（200 OK）

```json
{
  "id": "video-1701234567",
  "model": "grok-imagine-0.9",
  "created": 1701234567,
  "video_url": "https://grok.com/imagine/abc123def456",
  "status": "completed",
  "prompt": "让图片中的人物挥手微笑，背景有轻微的摇曳"
}
```

#### 响应字段说明

| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | string | 视频生成任务的唯一标识符 |
| model | string | 使用的模型名称 |
| created | integer | 创建时间戳（Unix时间戳，秒） |
| video_url | string | 生成的视频URL，可直接访问或下载 |
| status | string | 生成状态，成功时为 "completed" |
| prompt | string | 使用的提示词 |

---

## 错误响应

### 错误格式

所有错误响应遵循统一格式：

```json
{
  "error": {
    "message": "错误描述信息",
    "type": "错误类型",
    "code": "错误代码"
  }
}
```

### 常见错误

#### 1. 参数验证错误（400 Bad Request）

**图片URL为空**:
```json
{
  "error": {
    "message": "图片URL不能为空",
    "type": "validation_error",
    "code": "invalid_image_url"
  }
}
```

**图片URL格式错误**:
```json
{
  "error": {
    "message": "图片URL必须是http/https链接或base64格式（data:image/...）",
    "type": "validation_error",
    "code": "invalid_image_url"
  }
}
```

**模型不支持**:
```json
{
  "error": {
    "message": "模型 'xxx' 不是视频生成模型，请使用 grok-imagine-0.9",
    "type": "validation_error",
    "code": "invalid_model"
  }
}
```

**提示词为空**:
```json
{
  "detail": [
    {
      "type": "string_too_short",
      "loc": ["body", "prompt"],
      "msg": "String should have at least 1 character",
      "input": "",
      "ctx": {"min_length": 1}
    }
  ]
}
```

#### 2. 认证错误（401 Unauthorized）

```json
{
  "detail": "未授权访问"
}
```

#### 3. 视频生成失败（500 Internal Server Error）

**未获取到视频URL**:
```json
{
  "error": {
    "message": "视频生成失败：未能获取视频URL",
    "type": "video_generation_error",
    "code": "no_video_url"
  }
}
```

**Grok API错误**:
```json
{
  "error": {
    "message": "请求失败: 403 - 您的IP被拦截，请尝试以下方法之一: 1.更换IP 2.使用代理 3.配置CF值",
    "type": "HTTP_ERROR",
    "code": "HTTP_ERROR"
  }
}
```

**服务器内部错误**:
```json
{
  "error": {
    "message": "服务器内部错误",
    "type": "internal_error",
    "code": "internal_server_error"
  }
}
```

---

## 使用限制

1. **图片数量**: 每次请求只支持1张图片
2. **图片格式**: 支持常见图片格式（JPEG, PNG, GIF等）
3. **图片大小**: 建议不超过10MB
4. **提示词长度**: 建议在1-500字符之间
5. **速率限制**: 根据你的账户配置而定

---

## 最佳实践

### 1. 提示词编写建议

**清晰具体**:
```json
{
  "prompt": "让图片中的花朵在微风中轻轻摇曳，花瓣自然飘落"
}
```

**避免模糊**:
```json
{
  "prompt": "动起来"  // ❌ 太模糊
}
```

**描述动作和效果**:
```json
{
  "prompt": "人物眨眼微笑，背景云朵缓慢移动，添加柔和的光晕效果"
}
```

### 2. 图片选择建议

- 使用清晰、高质量的图片
- 主体明确的图片效果更好
- 避免过于复杂的场景
- 建议分辨率: 512x512 到 1024x1024

### 3. 错误处理

```python
import requests

def generate_video(image_url, prompt):
    url = "http://localhost:8001/v1/videos/generations"
    headers = {
        "Authorization": "Bearer YOUR_API_KEY",
        "Content-Type": "application/json"
    }
    data = {
        "image_url": image_url,
        "prompt": prompt
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=120)
        response.raise_for_status()
        result = response.json()
        return result['video_url']
    except requests.exceptions.HTTPError as e:
        error_detail = e.response.json()
        print(f"API错误: {error_detail}")
        raise
    except requests.exceptions.Timeout:
        print("请求超时，视频生成可能需要较长时间")
        raise
    except Exception as e:
        print(f"未知错误: {e}")
        raise

# 使用示例
try:
    video_url = generate_video(
        "https://example.com/image.jpg",
        "让图片动起来"
    )
    print(f"成功！视频URL: {video_url}")
except Exception as e:
    print(f"失败: {e}")
```

### 4. 视频URL处理

生成的视频URL可以：
- 直接在浏览器中打开查看
- 下载到本地存储
- 嵌入到网页中播放

```python
import requests

def download_video(video_url, save_path):
    """下载生成的视频"""
    response = requests.get(video_url, stream=True)
    response.raise_for_status()

    with open(save_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    print(f"视频已保存到: {save_path}")

# 使用
download_video(
    "https://grok.com/imagine/abc123",
    "output.mp4"
)
```

---

## 完整示例

### Python 完整示例

```python
import requests
import time
import os

class VideoGenerator:
    def __init__(self, api_key, base_url="http://localhost:8001"):
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    def generate(self, image_url, prompt, model="grok-imagine-0.9"):
        """生成视频"""
        url = f"{self.base_url}/v1/videos/generations"
        data = {
            "image_url": image_url,
            "prompt": prompt,
            "model": model
        }

        print(f"正在生成视频...")
        print(f"图片: {image_url}")
        print(f"提示词: {prompt}")

        try:
            response = requests.post(url, headers=self.headers, json=data, timeout=120)
            response.raise_for_status()
            result = response.json()

            print(f"✓ 生成成功!")
            print(f"视频URL: {result['video_url']}")
            print(f"任务ID: {result['id']}")

            return result

        except requests.exceptions.HTTPError as e:
            error = e.response.json()
            print(f"✗ 生成失败: {error.get('error', {}).get('message', str(e))}")
            raise
        except Exception as e:
            print(f"✗ 请求错误: {e}")
            raise

    def download(self, video_url, save_dir="videos"):
        """下载视频"""
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)

        filename = f"video_{int(time.time())}.mp4"
        filepath = os.path.join(save_dir, filename)

        print(f"正在下载视频...")
        response = requests.get(video_url, stream=True)
        response.raise_for_status()

        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        print(f"✓ 视频已保存: {filepath}")
        return filepath

# 使用示例
if __name__ == "__main__":
    # 初始化
    generator = VideoGenerator(api_key="YOUR_API_KEY")

    # 生成视频
    result = generator.generate(
        image_url="https://example.com/beautiful-landscape.jpg",
        prompt="云朵缓慢移动，水面波光粼粼，树叶在微风中摇曳"
    )

    # 下载视频
    if result.get('video_url'):
        generator.download(result['video_url'])
```

---

## FAQ

### Q: 视频生成需要多长时间？
A: 通常需要30-120秒，取决于图片复杂度和服务器负载。

### Q: 生成的视频有多长？
A: 视频时长由模型自动决定，通常为3-10秒。

### Q: 可以控制视频的分辨率吗？
A: 目前视频分辨率由模型自动决定，建议使用高质量输入图片以获得更好效果。

### Q: 视频URL会过期吗？
A: 是的，视频URL可能会在一段时间后过期，建议及时下载保存。

### Q: 支持批量生成吗？
A: 当前接口每次只能生成一个视频，批量生成需要多次调用接口。

### Q: 遇到 403 错误怎么办？
A: 403错误通常表示IP被Cloudflare拦截，尝试：
   1. 配置代理
   2. 更换IP
   3. 联系管理员配置CF Clearance值

---

## 技术支持

如有问题或需要技术支持，请：
- 查看日志文件获取详细错误信息
- 检查API Key是否有效
- 确认网络连接正常
- 联系系统管理员

---

## 更新日志

### v1.0.0 (2025-11-30)
- 首次发布视频生成API
- 支持单图片输入
- 支持自定义提示词
- 集成Grok Imagine 0.9模型
