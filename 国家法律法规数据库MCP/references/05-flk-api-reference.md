# flk.npc.gov.cn 二期 API 完整参考文档

> 基于 2026-05-12 实测验证。flk 于 2025年8月20日完成二期升级，旧 API（`/api/`, `/api/detail`）已废弃。

---

## 概述

- **网站**：https://flk.npc.gov.cn
- **技术栈**：Vue 3 + Vite SPA，后端 RuoYi (Java Spring Boot)
- **API 基础路径**：`/law-search/`
- **认证**：无（所有接口无需 token、captcha、session）
- **编码**：`Content-Type: application/json;charset=utf-8`
- **Windows 注意**：JSON body 中文必须 Unicode 转义（requests 默认 `ensure_ascii=True`）

---

## 通用请求头

```python
HEADERS = {
    "Content-Type": "application/json;charset=utf-8",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}
```

---

## 1. 搜索接口

### POST `/law-search/search/list`

**功能**：关键词搜索法规

**请求体**：
```json
{
  "searchRange": 1,
  "searchContent": "专利",
  "searchType": 2,
  "sxx": [3],
  "sxrq": [],
  "gbrq": [],
  "gbrqYear": [],
  "flfgCodeId": [],
  "zdjgCodeId": [],
  "xgzlSearch": false,
  "pageNum": 1,
  "pageSize": 100
}
```

**参数说明**：

| 参数 | 类型 | 说明 |
|------|------|------|
| searchRange | int | 1=标题搜索, 2=正文搜索 |
| searchContent | string | 搜索关键词（Unicode 转义） |
| searchType | int | 1=精确匹配, 2=模糊匹配 |
| sxx | int[] | 时效性过滤：1=已废止, 2=已修改, 3=有效。空数组=全部 |
| sxrq | string[] | 施行日期范围 |
| gbrq | string[] | 公布日期范围 |
| gbrqYear | string[] | 公布日期年份过滤 |
| flfgCodeId | int[] | 法律法规分类 codeId |
| zdjgCodeId | int[] | 制定机关 codeId |
| xgzlSearch | bool | 是否搜索相关资料 |
| pageNum | int | 页码（从1开始） |
| pageSize | int | 每页条数：10/20/30/40/50/100 |

**响应**：
```json
{
  "code": 200,
  "msg": "查询成功",
  "total": 52,
  "rows": [
    {
      "bbbs": "ff808081752b7d430175e4651cbd1547",
      "title": "中华人民共和国<em class='highlight'>专利</em>法",
      "gbrq": "2020-10-17",
      "sxrq": "2021-06-01",
      "sxx": "3",
      "flxz": "法律",
      "zdjgName": "全国人民代表大会常务委员会",
      "zdjgCodeId": "110",
      "flfgCodeId": "120",
      "score": 15.468875,
      "titleHightLightList": [...]
    }
  ]
}
```

**实测搜索结果数（sxx=[3] 现行有效）**：

| 关键词 | 结果数 |
|--------|--------|
| 专利 | 52 |
| 商标 | 10 |
| 著作权 | 35 |
| 不正当竞争 | 8 |
| 反垄断 | 11 |
| 知识产权 | 63 |

---

## 2. 详情接口

### GET `/law-search/search/flfgDetails?bbbs={bbbs}`

**功能**：获取法规完整元数据、结构树、文件路径、历史版本

**响应**：
```json
{
  "bbbs": "ff808081752b7d430175e4651cbd1547",
  "title": "中华人民共和国专利法",
  "gbrq": "2020-10-17",
  "sxrq": "2021-06-01",
  "sxx": 3,
  "flxz": "法律",
  "zdjgName": "全国人民代表大会常务委员会",
  "ossFile": {
    "ossWordPath": "prod/20201017/xxx.docx",
    "ossWordOfdPath": "prod/20201017/xxx.ofd",
    "ossWordOfdSize": 183797,
    "ossPdfPath": "prod/20201017/xxx.pdf",
    "ossPdfOfdPath": "prod/20201017/xxx.ofd",
    "ossPdfOfdSize": 864417
  },
  "lsyg": [
    {"bbbs": "...", "title": "中华人民共和国专利法", "gbrq": "2020-10-17", "highLight": true},
    {"bbbs": "...", "title": "中华人民共和国专利法", "gbrq": "2008-12-27", "highLight": false}
  ],
  "xgwj": [],
  "xgzl": [],
  "content": {
    "id": "...",
    "parentId": "00000000-0000-0000-0000-000000000000",
    "title": "中华人民共和国专利法",
    "index": 0,
    "children": [
      {"id": "...", "title": "题注", "children": []},
      {"id": "...", "title": "目录", "children": []},
      {
        "id": "...",
        "title": "第一章 总则",
        "children": [
          {"id": "...", "title": "第一条", "children": []},
          {"id": "...", "title": "第二条", "children": []}
        ]
      }
    ]
  }
}
```

**关键字段说明**：

| 字段 | 说明 |
|------|------|
| sxx | 时效性：3=现行有效, 2=已修改, 1=已废止, 4=尚未生效 |
| flxz | 法律性质：法律/行政法规/司法解释/部门规章等 |
| content | 结构树（仅含章/节/条标题，无条文正文） |
| lsyg | 历史沿革，highLight=true 表示当前版本 |
| ossFile | DOCX/PDF/OFD 文件路径（需通过下载接口获取签名URL） |

---

## 3. 下载接口

### 3.1 单文件下载

**GET `/law-search/download/pc?format=docx&bbbs={bbbs}&fileId=`**

**参数**：
- `format`：`"docx"` 或 `"pdf"`
- `bbbs`：法规唯一ID
- `fileId`：可为空

**响应**：
```json
{
  "code": 200,
  "data": {
    "url": "https://flkoss.obs-bj2.cucloud.cn/...?X-Amz-Algorithm=...&X-Amz-Signature=...",
    "urlIn": "http://172.16.x.x/..."
  }
}
```

- `url`：外网签名URL，有效期约1小时（`X-Amz-Expires=3599`）
- `urlIn`：内网地址（忽略）

**已验证**：专利法 DOCX 34KB、PDF 851KB 下载成功。

### 3.2 批量下载

**POST `/law-search/download/batch`**

**请求体**：
```json
[
  {"bbbs": "xxx", "format": "docx"},
  {"bbbs": "yyy", "format": "pdf"}
]
```

**响应**：
```json
{
  "code": 200,
  "data": [
    {"url": "https://flkoss.obs-bj2.cucloud.cn/...", "urlIn": "..."},
    {"url": "https://flkoss.obs-bj2.cucloud.cn/...", "urlIn": "..."}
  ]
}
```

**注意**：`format` 字段必填，缺少会返回 500。

### 3.3 移动端直接下载

**GET `/law-search/download/mobile?format=docx&bbbs={bbbs}&fileId=`**

直接返回文件二进制流（Content-Type 正确），不返回 JSON。

### 3.4 导出法规目录 Excel

**POST `/law-search/download/excel`**

**请求体**：bbbs 字符串数组 `["bbbs1", "bbbs2"]`

**响应**：直接返回 Excel 文件（XLS 格式）。

---

## 4. 枚举/元数据接口

### 4.1 分类枚举

**GET `/law-search/search/enumData`**

**响应**：返回两个分类树 `flfgfl`（法律法规分类）和 `zdjgfl`（制定机关分类）。

**法律法规分类树（flfgfl）**：

```
100  宪法
101  法律
  102    法律
    110    宪法相关法
    120    民法商法          ← 专利法、商标法、著作权法
    130    行政法
    140    经济法            ← 反不正当竞争法、反垄断法
    150    社会会
    155    生态环境法
    160    刑法
    170    诉讼与非诉讼程序法
  180    法律解释
  190    有关法律问题和重大问题的决定（部分）
  195    修正案
  200    修改、废止的决定
201  行政法规
  210    行政法规            ← 各种实施细则/条例
  215    修改、废止的决定
220  监察法规
221  地方法规
  222    地方法规
    230    地方性法规
    260    自治条例
    270    单行条例
    290    经济特区法规
    295    浦东新区法规
    300    海南自由贸易港法规
  305    法规性决定
  310    修改、废止的决定
311  司法解释
  320    高法司法解释
  330    高检司法解释
  340    联合发布司法解释
  350    修改、废止的决定
```

**制定机关分类树（zdjgfl）**：

```
90   全国人大及其常委会
  100    全国人大
  110    全国人大常委会
120  国务院
130  国家监察委员会
140  最高人民法院
150  最高人民检察院
165  地方人大及其常委会
  170-470  各省/自治区/直辖市
```

**实测 flfgCodeId 对照**：

| 法规 | flxz | flfgCodeId | zdjgCodeId |
|------|------|-----------|------------|
| 专利法 | 法律 | 120 | 110 |
| 专利法实施细则 | 行政法规 | 210 | 120 |
| 商标法 | 法律 | 120 | 110 |
| 商标法实施条例 | 行政法规 | 210 | 120 |
| 著作权法 | 法律 | 120 | 110 |
| 反不正当竞争法 | 法律 | 140 | 110 |
| 反垄断法 | 法律 | 140 | 110 |
| 垄断民事纠纷司法解释 | 司法解释 | 320 | 140 |

### 4.2 首页聚合

**GET `/law-search/index/aggregateData`**

返回：法律分类统计（flflCount）、新法速递（xfsd）、热门搜索、热门下载。

### 4.3 搜索联想

**GET `/law-search/prompts/search?title={keyword}`**

返回搜索建议列表。

### 4.4 相关推荐

**GET `/law-search/search/recommend?bbbs={bbbs}`**

返回基于当前法规的推荐列表。

---

## 5. 文件预览接口

### GET `/law-search/amazonFile/previewLink?filePath={ossPath}`

返回 OFD 在线阅读器 URL：`{"code": 200, "data": {"url": "https://flkofd.npc.gov.cn/reader?file=..."}}`

---

## 6. Pandoc 转换格式参考

### 原始 DOCX 经 pandoc 转换后的格式特征

```bash
pandoc input.docx -t markdown --wrap=none -o output.md
```

**输出特征**：

| 元素 | pandoc 输出 | 目标 Obsidian 格式 |
|------|------------|-------------------|
| 法律名称 | 纯文本 | YAML `title` + H1 |
| 题注 | `> （1984年...修正）` | 普通段落（去 `>`） |
| 目录 | `目　　录` + blockquote | 删除 |
| 章标题 | `第一章　总　　则`（纯文本） | `# **第一章 总 则**` |
| 条标题 | `第一条　为了...`（同行） | `## **第一条**\n\n为了...` |
| 款 | 空行分隔 | 一致 |
| 列举项 | `（一）...` 空行分隔 | 基本一致 |
| 全角空格 | `　` 大量出现 | 替换为半角 |

### 转换所需的后处理步骤

1. 删除目录部分（`目　　录` 到 blockquote 结束）
2. 清理全角空格（`　` → ` `）
3. 去除题注 blockquote 标记（`> ` → ` `）
4. 章标题加 H1 粗体（`第一章 ...` → `# **第一章 ...**`）
5. 条标题拆分（`第X条　内容` → `## **第X条**\n\n内容`）
6. 添加 YAML frontmatter + 元数据表格

### 已下载的测试文件

| 文件 | 位置 | 用途 |
|------|------|------|
| 专利法 DOCX | `D:/tmp/flk_patent_law.docx` | 格式转换测试 |
| 专利法 pandoc 输出 | `D:/tmp/flk_patent_law_raw.md` | 后处理参考 |
| 专利法详情 JSON | `D:/tmp/flk_patent_law_detail.json` | 元数据字段参考 |
| 商标法 DOCX | `D:/tmp/flk_trademark_law.docx` | 格式转换测试 |
| 商标法 pandoc 输出 | `D:/tmp/flk_trademark_law_raw.md` | 后处理参考 |
| 商标法详情 JSON | `D:/tmp/flk_trademark_law_detail.json` | 元数据字段参考 |

---

## 7. 现有数据库状态值参考

现有 119 篇法规的 `状态` 字段值分布：

| 值 | 数量 | 对应 flk sxx |
|----|------|-------------|
| `[生效中]` | 87 | sxx=3 |
| 空 | 16 | — |
| `[被修订]` | 2 | sxx=2 |
| `[未生效]` | 1 | sxx=4 |

**映射规则**：
- sxx=3 → `[生效中]`
- sxx=2 → `[被修订]`
- sxx=1 → `[已废止]`（数据库中暂无此值）
- sxx=4 → `[未生效]`

---

## 8. 速率限制与可靠性

- **实测**：连续约 20 次请求后被限流（返回空响应）
- **建议**：请求间隔 0.5s，pageSize=100 减少请求次数
- **重试策略**：失败重试 3 次，间隔递增（1s/2s/4s）
- **缓存**：已下载的 DOCX 缓存到 `data/content_cache/`，避免重复下载
