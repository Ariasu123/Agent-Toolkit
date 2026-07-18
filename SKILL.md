---
name: weekly-report
description: 生成科研周报 DOCX，维护已用文献 used.md，自动寻找不重复且相近方向的文献，按固定模板填写本周目标、本周进展、图片、下周计划、周次日期和文献精读表格。
---

# 周报生成 Skill

当用户要生成新的科研周报、同步已读文献清单、或替换周报里的“本周文献精读”部分时，使用这个 skill。

优先使用随 skill 附带的脚本：

```bash
python3 scripts/weekly_report.py --help
```

脚本依赖 `python-docx`。如果需要插入图片，运行环境还应安装 `Pillow`。

## 目录和命名

默认周报目录是当前工作目录。也可以通过环境变量或命令行参数覆盖：

- `WEEKLY_REPORT_DIR` 或 `--report-dir`：周报目录
- `USED_FILE` 或 `--used-file`：已用文献清单路径，默认是周报目录下的 `used.md`
- `WEEKLY_REPORT_PREFIX` 或 `--report-prefix`：周报文件名前缀，默认是 `weekly-report`
- `WEEKLY_REPORT_CJK_FONT`：中文字体，默认是 `宋体`
- `WEEKLY_REPORT_RENDER_DOCX`：可选的 `render_docx.py` 路径，用于生成后版面检查

默认每周输入文件：

```text
$WEEKLY_REPORT_DIR/weekly-input.md
```

默认图片归档目录建议：

```text
$WEEKLY_REPORT_DIR/images/YYMMDD/
```

例如生成 `student-weekly-report-260719.docx` 时，本周图片建议放在：

```text
$WEEKLY_REPORT_DIR/images/260719/
```

## 用户输入格式

如果用户没有按固定格式给本周内容，先请用户把 `weekly-input.md` 改成下面的 Markdown 结构：

```markdown
## 本周目标和方案
1. ...
2. ...

## 本周进展和问题
这里写本周进展文字。

图片:
- images/260719/result1.png
- images/260719/result2.jpg

## 下周研究计划
1. ...
2. ...

## 其他
无
```

处理规则：

- “本周目标和方案”和“下周研究计划”必须保留用户原文，包括编号、换行和措辞。
- “本周进展和问题”支持文字和图片。
- 如果没有提供图片路径，生成新周报时删除模板里的旧图片，避免误留上周图片。
- 如果提供多张图片，按纵向逐张插入在进展文字后方，按页面可用宽度缩放，不加图题。
- 图片路径可以写绝对路径，也可以写相对路径；相对路径以 `weekly-input.md` 所在目录为基准。
- “其他”默认写 `无`，除非用户显式提供其他内容。

## 标准流程

### 1. 同步 used.md

```bash
python3 scripts/weekly_report.py sync-used \
  --report-dir /path/to/reports \
  --report-prefix student-weekly-report
```

脚本会扫描周报目录下匹配 `前缀-YYMMDD.docx` 或 `前缀-YY-MMDD.docx` 的文件，读取“本周文献精读”表格中的文献信息，并维护 `used.md`。

`used.md` 规则：

- 一篇论文只保留一行。
- 优先用 DOI 去重；没有 DOI 时用规范化后的题名去重。
- 同一篇论文如果在多个周报中出现，放在同一行的“出现记录”里。

### 2. 自动选择未用文献

```bash
python3 scripts/weekly_report.py select-paper \
  --report-dir /path/to/reports \
  --report-prefix student-weekly-report \
  --out /tmp/weekly-paper.json
```

选择规则：

- 优先选择 2021 年以后的强相关文献。
- 方向优先级：中红外气体传感、计算型光谱仪、光谱重建、微型光谱仪、滤波阵列光谱仪。
- 优先使用 Crossref、DOI、出版社或官方元数据。
- 排除 `used.md` 中已出现过的 DOI 或题名。
- 如果没有强相关近年文献，自动放宽到更早或相邻方向；仍找不到时停止并说明原因，不编造文献。

### 3. 准备文献精读内容

读取 `/tmp/weekly-paper.json`，必要时再查 DOI 或出版社页面。然后写一个 JSON 文件，例如 `/tmp/weekly-literature.json`：

```json
{
  "citation": "...",
  "corresponding_author_unit": "...",
  "research_purpose": "...",
  "research_methods": "...",
  "conclusions": "...",
  "lessons": "...",
  "critique": "..."
}
```

写作要求：

- 使用正式中文周报语气。
- “从论文中学习到的内容”和“批判性思维”要尽量联系当前红外气体传感或计算型光谱仪工作。
- 如果不能可靠确认通讯作者单位，不要猜测；写成有来源支撑的作者或单位信息。

### 4. 生成新周报

默认读取周报目录下的 `weekly-input.md`：

```bash
python3 scripts/weekly_report.py generate \
  --report-dir /path/to/reports \
  --report-prefix student-weekly-report \
  --paper /tmp/weekly-paper.json \
  --literature /tmp/weekly-literature.json
```

也可以自动选文献并生成元数据草稿：

```bash
python3 scripts/weekly_report.py generate \
  --report-dir /path/to/reports \
  --report-prefix student-weekly-report \
  --auto-paper
```

如需临时使用其他输入文件，可以显式传入：

```bash
python3 scripts/weekly_report.py generate \
  --report-dir /path/to/reports \
  --report-prefix student-weekly-report \
  --input /absolute/path/to/other-input.md \
  --paper /tmp/weekly-paper.json \
  --literature /tmp/weekly-literature.json
```

默认日期规则：

- 复制目录中日期最新的匹配前缀周报作为模板。
- 新周报默认以上一份周报的结束日期为起点，再往后一周。
- 例如最新周报是 `周次：2026.7.5-7.12`，新周报写成 `周次：2026.7.12-7.19`。
- 可以用 `--week-ending YYYY-MM-DD` 手动指定本周结束日期。

文件名规则：

- 输出为 `前缀-YYMMDD.docx`。
- 不覆盖已有文件；如目标文件已存在，则自动写成 `前缀-YYMMDD-v2.docx`、`-v3.docx` 等。

### 5. 版面检查和交付

`generate` 默认尝试渲染 DOCX，生成内部 QA 图片。如果渲染工具不可用，脚本会继续生成 DOCX 并报告渲染跳过或失败。

交付时只需要告诉用户：

- 新 `.docx` 路径
- `used.md` 是否已同步
- 是否完成渲染检查

除非用户明确要求，不要把 QA PDF/PNG 当作最终交付物。

## 常用命令

只解析用户输入，不写 Word：

```bash
python3 scripts/weekly_report.py parse-input
```

生成周报但跳过渲染：

```bash
python3 scripts/weekly_report.py generate --auto-paper --no-render
```

重新同步 used.md：

```bash
python3 scripts/weekly_report.py sync-used
```
