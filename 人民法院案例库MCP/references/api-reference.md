# 人民法院案例库 API 参考文档

> 调查日期：2026-05-14
> 网站地址：https://rmfyalk.court.gov.cn

---

## 一、认证

### Token 获取

从浏览器 Cookie 中获取 `faxin-cpws-al-token`，JWT 格式，有效期约 4 小时。

```
faxin-cpws-al-token=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
```

### Token 传递方式

所有 API 请求需携带 HTTP Header：

```
faxin-cpws-al-token: {token}
```

### 认证流程

1. 用户在 `account.court.gov.cn` 登录
2. SSO 回调写入 Cookie `faxin-cpws-al-token`
3. 前端 JS 从 Cookie 读取，附加到所有 API 请求 Header

### Token 刷新

- JWT 有效期约 4 小时（3600 秒 Max-Age）
- 过期后需重新登录网站获取新 Token
- 无 API 刷新机制

### 公开 API（无需 Token）

- `cpwsAl/indexTongji` — 首页统计数据

---

## 二、API 基础

### Base URL

```
https://rmfyalk.court.gov.cn/cpws_al_api/api/
```

### 通用请求头

```
Content-Type: application/json;charset=UTF-8
faxin-cpws-al-token: {token}
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)
Referer: https://rmfyalk.court.gov.cn/view/list.html
Origin: https://rmfyalk.court.gov.cn
```

### 通用响应格式

```json
{
  "code": 0,          // 0=成功, 401=未登录, 500=错误
  "msg": "获取成功！",
  "data": { ... }
}
```

---

## 三、搜索 API（核心）

### 端点

```
POST /cpwsAl/search
```

### 请求体

```json
{
  "page": 1,
  "size": 10,
  "lib": "qb",
  "searchParams": {
    "userSearchType": 1,
    "isAdvSearch": "0",
    "selectValue": ["qw"],
    "lib": "cpwsAl_qb",
    "sort_field": "",
    "keyTitle": ["关键词"]
  }
}
```

### 顶层参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `page` | int | 页码，从 1 开始 |
| `size` | int | 每页条数，支持 10/20/30/50 |
| `lib` | string | 案例库范围（见下表） |
| `pdh` | int | 聚类分页参数（仅聚类 API 使用） |

### searchParams 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `userSearchType` | int | 检索类型：1=精确, 2=模糊 |
| `isAdvSearch` | string | **"0"=一般检索, "1"=高级检索** |
| `selectValue` | **string[]** | ⚠️ 检索字段，**必须是数组** |
| `lib` | string | 案例库筛选（见下表） |
| `sort_field` | string | 排序字段（见排序说明） |

### selectValue 检索字段（一般检索）

| 值 | 说明 |
|----|------|
| `qw` | 全文（默认） |
| `title` | 标题 |
| `albh` | 案例编号 |
| `cprq` | 裁判日期 |
| `keyword` | 关键词 |
| `jbaq` | 基本案情 |
| `cply` | 裁判理由 |

⚠️ **必须用数组格式**：`["qw"]`，不能用字符串 `"qw"`（会返回全部 5396 条）。

### lib 案例库范围

| 值 | 说明 |
|----|------|
| `cpwsAl_qb` | 全部案例 |
| `cpwsAl_01` | 指导性案例 |
| `cpwsAl_02` | 参考案例 |

### sort_field 排序

| 值 | 说明 |
|----|------|
| `""` | 相关性（默认） |
| `-cpws_al_no` | 案例编号降序 |
| `+cpws_al_no` | 案例编号升序 |
| `-cpws_al_zs_date` | 裁判时间降序 |
| `+cpws_al_zs_date` | 裁判时间升序 |

### 搜索结果数据结构

```json
{
  "totalCount": 417,
  "datas": [{
    "id": "URL编码的ID",
    "cpws_al_id": "URL编码的ID",
    "cpws_al_type": "01",
    "cpws_al_status": "01",
    "cpws_al_no": "2021-18-2-160-001",
    "cpws_al_title": "指导案例158号：...",
    "cpws_al_case_sort_id": ["02", "A02"],
    "cpws_al_case_sort_name": "民事",
    "cpws_al_sort_name": "专利权权属、侵权纠纷",
    "cpws_al_slfy_name": "最高人民法院",
    "cpws_al_zs_date": "2019.12.30",
    "cpws_al_ajzh": "（2019）最高法民申6342号",
    "cpws_al_slcx_name": "再审",
    "cpws_al_cpyz": "<p>裁判要点...</p>",
    "cpws_al_keyword": ["民事", "专利权权属"],
    "cpws_al_infos": "编号 / 类型 / 案由 / 法院 / 日期 / 案号 / 程序 / 入库日期",
    "cpws_al_rk_time": "2023-08-24 14:55:00",
    "cpws_al_source_id": ["0101"]
  }]
}
```

### 字段映射

| 字段 | 值 | 说明 |
|------|-----|------|
| `cpws_al_type` | `"01"` | 指导性案例 |
| | `"02"` | 参考案例 |
| | `"04"` | 特色案事例 |
| `cpws_al_status` | `"01"` | 有效 |
| | `"02"` | 失效 |

---

## 四、高级检索

### 触发方式

将 `isAdvSearch` 设为 `"1"`，在 `searchParams` 中添加需要过滤的字段。

### 高级检索字段

| 字段名 (key) | 说明 | 类型 | 值格式 |
|-------------|------|------|--------|
| `keyTitle` | 标题 | 文本输入 | 关键词字符串 |
| `keyContent` | 全文 | 文本输入 | 关键词字符串 |
| `cpws_al_no` | 案例编号 | 文本输入 | 如 `2021-18-2-160-001` |
| `cpws_al_ajzh` | 案号 | 文本输入 | 如 `（2019）最高法民申6342号` |
| `sort_id_cpwsAl` | 案由/罪名 | 下拉选择 | 分类代码 |
| `case_sort_id_cpwsAl` | 案件类型 | 下拉选择 | `"02"`=民事, `"03"`=刑事, `"04"`=行政 等 |
| `slcx_id_cpwsAl` | 审理程序 | 下拉选择 | 分类代码 |
| `slfy_id_cpwsAl` | 审理法院 | 下拉选择 | 法院代码 |
| `fyjb_id_cpwsAl` | 法院级别 | 下拉选择 | `"03"`=最高人民法院 等 |
| `wslx_id_cpwsAl` | 文书类型 | 下拉选择 | 分类代码 |
| `keyword_cpwsAl` | 关键词 | 文本输入 | 关键词字符串 |

### 已验证的案件类型 (case_sort_id_cpwsAl)

| 值 | 说明 |
|----|------|
| `"02"` | 民事 |
| `"03"` | 刑事 |
| `"04"` | 行政 |

### 已验证的法院级别 (fyjb_id_cpwsAl)

| 值 | 说明 |
|----|------|
| `"03"` | 最高人民法院 |

### 高级检索示例

```json
{
  "page": 1,
  "size": 10,
  "lib": "qb",
  "searchParams": {
    "userSearchType": 1,
    "isAdvSearch": "1",
    "selectValue": ["qw"],
    "lib": "cpwsAl_qb",
    "sort_field": "",
    "keyTitle": ["专利权权属"],
    "case_sort_id_cpwsAl": "02",
    "fyjb_id_cpwsAl": "03"
  }
}
```

### 组合检索规则

- 多个条件同时存在时为 AND 关系
- `keyTitle` 支持数组（多关键词）
- 文本字段为空字符串时视为不筛选
- 高级检索中 `selectValue` 仍需为 `["qw"]`（值不影响高级检索逻辑）

---

## 五、案例详情 API

### 端点

```
POST /cpwsAl/content
```

### 请求体

```json
{
  "gid": "wClj3UsWG%2FasUNQmJ4og64hA%2BxZkh6jILYm3lU7c%2FXI%3D"
}
```

⚠️ `gid` 的值必须是 **URL 编码后的 cpws_al_id**（即搜索结果中原始的 `cpws_al_id` 字段值）。不需要二次编码。

### 详情响应字段

```json
{
  "code": 0,
  "data": {
    "isCanBrowse": "0",
    "data": {
      "cpws_al_id": "...",
      "cpws_al_type": "01",
      "cpws_al_title": "指导案例158号：...",
      "cpws_al_no": "2021-18-2-160-001",
      "cpws_al_ajzh": "（2019）最高法民申6342号",
      "cpws_al_zs_date": "2019.12.30",
      "cpws_al_cpyz": "<p>裁判要点HTML</p>",
      "cpws_al_jbaq": "<p>基本案情HTML</p>",
      "cpws_al_cpjg": "<p>裁判结果HTML</p>",
      "cpws_al_cply": "<p>裁判理由HTML（最长，含完整说理）</p>",
      "cpws_al_glsy": "<p>关联法条HTML</p>",
      "cpws_al_keyword": ["民事", "专利权权属", "职务发明创造"],
      "cpws_al_rk_time": "2023-08-24 14:55:00",
      "cpws_al_sort_name": "",
      "cpws_al_case_sort_id": ["02", "A02"]
    }
  }
}
```

### 详情核心字段说明

| 字段 | 内容 | 格式 |
|------|------|------|
| `cpws_al_cpyz` | 裁判要点（指导性）或裁判要旨（参考） | HTML `<p>` 标签 |
| `cpws_al_jbaq` | 基本案情（完整叙述） | HTML `<p><br/>` 标签 |
| `cpws_al_cpjg` | 裁判结果（一/二/再审结果） | HTML `<p>` 标签 |
| `cpws_al_cply` | 裁判理由（最长，含完整说理分析） | HTML `<p>` 标签 |
| `cpws_al_glsy` | 关联法条列表 | HTML `<p><br/>` 标签 |
| `cpws_al_keyword` | 关键词标签 | JSON 数组 |

---

## 六、聚类/统计 API

### 类型统计

```
POST /cpwsAl/cpwsAlTypeNextLeftCluster
```

返回指导性/参考案例各有多少条。

```json
{
  "code": 0,
  "data": [
    {"key": "01", "value": "指导性案例", "count": "21", "intCount": 21},
    {"key": "02", "value": "参考案例", "count": "396", "intCount": 396}
  ]
}
```

### 关键词聚类

```
POST /cpwsAl/keywordNextLeftCluster
```

返回搜索结果中的关键词分布。

### 审判年份聚类

```
POST /cpwsAl/yearNextLeftCluster
```

返回搜索结果按审判年份分布。

### 其他聚类端点

| 端点 | 说明 | 状态 |
|------|------|------|
| `sortNextLeftCluster` | 案由/罪名聚类 | 需特定条件触发 |
| `slfyNextLeftCluster` | 审理法院聚类 | 需特定条件触发 |
| `fyjbNextLeftCluster` | 法院级别聚类 | 需特定条件触发 |
| `slcxNextLeftCluster` | 审理程序聚类 | 需特定条件触发 |

---

## 七、其他 API

### 首页统计（公开，无需 Token）

```
GET /cpwsAl/indexTongji
```

### 用户信息

```
POST /user/getUserInfo
Body: {"state": "..."}
```

### 相关推荐案例

```
POST /cpwsAl/contentTop10
Body: {"gid": "URL编码的ID"}
```

### 案例下载

```
GET /cpwsAl/contentDownload?id={URL编码的ID}
```

### 用户互动

| 端点 | 方法 | 功能 |
|------|------|------|
| `user/isLikeFile` | POST | 检查是否点赞 |
| `user/likeFileCount` | POST | 点赞数 |
| `user/likeFile` | POST | 点赞 |
| `user/cancelLikeFile` | POST | 取消点赞 |
| `user/isCollectionFile` | POST | 检查是否收藏 |
| `user/collectionFile` | POST | 收藏 |
| `user/cancelCollectionFile` | POST | 取消收藏 |
| `user/getNoteFile` | POST | 获取笔记 |
| `user/noteFile` | POST | 保存笔记 |
| `user/feedbackFile` | POST | 反馈 |
| `user/recordSearchLog` | POST | 记录搜索日志 |

---

## 八、实测搜索统计

| 关键词 | 总数 | 指导性 | 参考 |
|--------|------|--------|------|
| 专利 | 417 | 21 | 396 |
| 商标 | 268 | — | — |
| 著作权 | — | — | — |
| 全部（无关键词） | 5396 | — | — |

---

## 九、已知限制

1. **Token 有效期短**（约 4 小时），需定期手动刷新
2. **无 API Key 机制**，完全依赖浏览器登录态
3. **下拉选择字段**（案由、法院等）的选项值需通过聚类 API 或 XML 文件获取
4. **部分聚类 API** 返回空结果，可能需要先执行搜索才能触发
5. **Windows 编码问题**：JSON body 中中文需用 `ensure_ascii=True`（默认行为）

---

## 十、Python 调用示例

```python
import urllib.request, json, ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

BASE = 'https://rmfyalk.court.gov.cn/cpws_al_api/api/'
TOKEN = 'your_token_here'

def api_post(path, body=None):
    data = json.dumps(body or {}).encode('utf-8')
    req = urllib.request.Request(BASE + path, data=data, method='POST')
    req.add_header('faxin-cpws-al-token', TOKEN)
    req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)')
    req.add_header('Content-Type', 'application/json')
    req.add_header('Referer', 'https://rmfyalk.court.gov.cn/view/list.html')
    req.add_header('Origin', 'https://rmfyalk.court.gov.cn')
    with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
        return json.loads(resp.read().decode('utf-8'))

# 一般检索：搜索"专利"
result = api_post('cpwsAl/search', {
    'page': 1, 'size': 10, 'lib': 'qb',
    'searchParams': {
        'userSearchType': 1, 'isAdvSearch': '0',
        'selectValue': ['qw'], 'lib': 'cpwsAl_qb',
        'sort_field': '', 'keyTitle': ['专利']
    }
})
print(f"共 {result['data']['totalCount']} 条结果")

# 获取详情
first = result['data']['datas'][0]
detail = api_post('cpwsAl/content', {'gid': first['cpws_al_id']})
print(detail['data']['data']['cpws_al_title'])
```
