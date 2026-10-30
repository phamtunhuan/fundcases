# 私募基金监管处罚案例库

收录 **中国证券投资基金业协会**「自律管理 → 纪律处分 → 受处分机构」栏目全量案例，并构建为可检索的静态网站（GitHub Pages）。

- 案例总数：**597 例**（2015-01 ~ 2026-10）
- 数据来源：https://www.amac.org.cn/zlgl/jlcf/scfjg/index.html
- 在线站点：`docs/` 目录，直接用 GitHub Pages 发布

## 检索能力

前端为**零依赖**实现，搜索按「全角归一化 → 去标点 → 分词 → 字段加权打分」处理：

| 能力 | 说明 |
|------|------|
| 多关键词 | 空格分隔，**AND 语义**（全部命中才显示），如 `深圳 挪用`、`适当性 2023` |
| 短语锁定 | 用英文或中文引号包裹，如 `"投资者适当性"` |
| 字段加权 | 机构名（完全匹配 130 / 前缀 78 / 包含 48）＞ 标题 26 ＞ 类型·地区·措施·事由·登记编号 15 ＞ 决定理由 8 ＞ 正文全文 4 |
| 相关度排序 | 有关键词时按得分降序，同分按日期降序 |
| 正文全文 | 勾选「全文」或元数据零命中时自动加载 `texts.json` 建立索引，可搜决定书任意词句 |
| 中文近似 | 纯中文长词（≥4 字）整体未命中时，允许在同一字段内二字组全覆盖的近似匹配 |
| 命中提示 | 列表高亮关键词并给出正文摘要；详情页自动定位到首个命中词 |
| 可分享 | 检索条件同步到地址栏（`?q=...&type=...`），链接可直接分享 |

## 目录结构

```
scripts/
  crawl_list.py        抓取 35 个列表页，产出 data/cases_raw_list.json
  download_docs.py     并发下载 597 份原文（480 PDF + 117 网页）
  ocr_vision.py        扫描版 PDF 的 macOS Vision 中文 OCR
  parse_html.py        抽取网页版决定书正文
  build_json.py        整合元数据 + 正文，打标签，产出案例 JSON
  build_site_data.py   拆分索引/正文，输出到 docs/data/
data/
  cases_raw_list.json           列表元数据（597 条）
  amac_penalty_cases.json        全量结构化案例（含正文，3.4 MB）
  amac_penalty_cases_slim.json   同上去掉正文（543 KB）
  raw/docs/                      原始 PDF / HTML（542 MB，不入库）
  ocr/                           OCR 文本（不入库）
docs/
  index.html            网站首页
  assets/{style.css,app.js}
  data/cases.json        检索索引（444 KB，页面加载）
  data/texts.json        决定书正文（2.8 MB，点击后懒加载）
```

## 数据字段

| 字段 | 说明 |
|---|---|
| `title` / `date` / `year` | 原标题、发布日期、年份 |
| `doc_type` | 纪律处分决定书 / 复核决定书 / 事先告知书送达公告 / 注销登记公告 等 |
| `doc_format` | `pdf`（扫描件）或 `html`（网页版） |
| `parties` / `organizations` / `individuals` | 当事人、机构、自然人 |
| `org_primary` | 主责机构名称 |
| `manager_type` | 管理人类型（固定五类）：私募证券投资基金管理人 / 私募股权、创业投资基金管理人 / 其他私募投资基金管理人 / 私募资产配置类管理人 / 未填报管理人类型 |
| `manager_type_source` | 类型来源：协会公示（在册/已注销）/ 正文推断 |
| `registry_status` | 协会公示登记状态，仅两类：**在册 / 已注销** |
| `name_changed` | 协会在册、注销两处公示均查不到该名称时为 `true`，推定管理人已变更名称（此时 `registry_status` 记为「已注销」） |
| `register_no` | 协会登记编号（P******） |
| `legal_rep` | 法定代表人 |
| `member_type` | 协会会员类型 |
| `registry_url` | 协会公示页链接 |
| `region` | 地区（优先取正文「XX证监局」，其次机构名称前缀） |
| `penalties` | 处分措施：撤销管理人登记、取消会员资格、公开谴责、警告等 15 类 |
| `violation_tags` | 违规事由标签：投资者适当性、募集行为违规、挪用侵占基金财产等 20 类 |
| `source_url` | 协会原文链接 |
| `text` | 决定书正文（已做段落合并，PDF 部分为 OCR 文本） |
| `penalty_text` | 处分决定原文短句（如「撤销前海昆桐管理人登记」），用于核对措施标注 |
| `decision_text` | 处分决定章节原文（≤1200 字） |

### 正文与字段的精度处理

- **排版**：OCR 按视觉行输出会切碎中文段落。`build_json.py` 的 `reflow()` 依据缩进与编号（一、（一）1.）识别段落边界，段内直接拼接，输出连贯段落。
- **OCR 容错**：扫描件错字会击穿关键词匹配（「撒销/撇销/撖销」→撤销、「皙儜」→暂停、「遣贵/谴费」→谴责）。匹配前先做 OpenCC 繁简统一 + 错字映射归一化，存储原文仍保留 OCR 原貌。
- **措施标注**：只在「协会决定作出以下纪律处分：XXX。」这句中匹配，避免法规引用与套话段落误命中；「撤销」与「注销」互斥。
- **地区**：正文「XX证监局」> 机构名称所在地（含括号内地名，如「中财鼎盛（北京）…」）> 正文省市。
- **管理人类型（协会公示核对）**：`query_amac_type.py` 逐机构调用协会公示接口——先查「私募基金管理人公示」(在册, `primaryInvestType`)，未命中再查「已注销私募基金管理人公示」列表并由详情页提取「机构类型」。机构名匹配置信度：93% 精确相等、7% 简称↔全称（含关系+相似度阈值 0.82）、其余标注 `未查到` 回退正文推断。524 个机构命中 496（94.7%）。查询结果缓存于 `data/manager_types.json`。

## 重建数据

```bash
python scripts/crawl_list.py        # 1. 抓列表
python scripts/download_docs.py     # 2. 下载原文
python scripts/ocr_vision.py        # 3. OCR（仅 macOS，需 pip install pyobjc-framework-Vision pyobjc-framework-Quartz）
python scripts/parse_html.py        # 4. 抽网页版正文
python scripts/build_json.py        # 5. 整合打标签
python scripts/build_site_data.py   # 6. 产出网站数据
```

## 发布到 GitHub Pages

1. 提交 `docs/` 与 `data/*.json` 到仓库
2. 仓库 Settings → Pages → Source 选择 `main` 分支的 `/docs` 目录
3. 等待构建完成即可访问 `https://<用户名>.github.io/<仓库名>/`

本地预览（需 HTTP 协议，file:// 会被浏览器拦截数据请求）：

```bash
cd docs && python -m http.server 8000
```

## 免责声明

管理人类型、地区、处分措施与违规事由均为程序自动标注，PDF 正文经 OCR 识别可能存在误差，仅供合规研究参考，引用请以协会原文为准。
