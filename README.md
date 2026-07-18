# weekly-report

一个用于生成科研周报 DOCX 的 Codex skill。它可以扫描历史周报维护 `used.md` 已用文献清单，自动寻找未重复的相关文献，读取每周输入 Markdown，并按既有 Word 模板生成新的周报。


## 功能

- 扫描历史 `.docx` 周报并维护 `used.md`
- 按 DOI 或题名去重已用文献
- 从 Crossref 搜索未重复的相关论文
- 读取 `weekly-input.md` 中的本周目标、进展、图片、下周计划和其他内容
- 替换 Word 模板中的正文区块和“本周文献精读”表格
- 自动更新周次日期
- 按 `前缀-YYMMDD.docx` 命名新周报，遇到重名自动生成 `-v2`、`-v3`

## 安装为 Codex Skill

将仓库克隆到 Codex skills 目录下，例如：

```bash
git clone https://github.com/<your-name>/weekly-report-skill.git \
  ~/.codex/skills/weekly-report
```

重启 Codex 后，skill 会以 `weekly-report` 的名字被发现。

也可以只把本仓库作为普通脚本使用：

```bash
cd weekly-report-skill
python3 scripts/weekly_report.py --help
```

## 依赖

脚本需要 Python 3，并依赖：

```bash
python3 -m pip install python-docx Pillow
```

如果只处理无图片周报，核心依赖是 `python-docx`。如果需要插入图片，建议安装 `Pillow`。

## 周报目录约定

准备一个周报工作目录，例如：

```text
/path/to/reports/
```

目录中建议包含：

```text
weekly-input.md
used.md
images/YYMMDD/
student-weekly-report-260712.docx
```

脚本默认把当前目录当作周报目录，也可以用环境变量或命令行参数指定：

```bash
export WEEKLY_REPORT_DIR=/path/to/reports
export WEEKLY_REPORT_PREFIX=student-weekly-report
```

常用配置：

- `WEEKLY_REPORT_DIR` 或 `--report-dir`：周报目录
- `USED_FILE` 或 `--used-file`：已用文献清单，默认是周报目录下的 `used.md`
- `WEEKLY_REPORT_PREFIX` 或 `--report-prefix`：周报文件名前缀，默认是 `weekly-report`
- `WEEKLY_REPORT_CJK_FONT`：中文字体，默认是 `宋体`
- `WEEKLY_REPORT_RENDER_DOCX`：可选的 `render_docx.py` 路径，用于生成后版面检查

## weekly-input.md 格式

每周只需要覆盖更新周报目录下的 `weekly-input.md`：

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

图片路径可以写绝对路径，也可以写相对路径。相对路径以 `weekly-input.md` 所在目录为基准。

如果没有图片，省略 `图片:` 段即可。脚本会移除模板中旧的图片，避免误留上周内容。

## 使用

同步已用文献：

```bash
python3 scripts/weekly_report.py sync-used \
  --report-dir /path/to/reports \
  --report-prefix student-weekly-report
```

自动选择未用文献：

```bash
python3 scripts/weekly_report.py select-paper \
  --report-dir /path/to/reports \
  --report-prefix student-weekly-report \
  --out /tmp/weekly-paper.json
```

解析本周输入：

```bash
python3 scripts/weekly_report.py parse-input \
  --report-dir /path/to/reports
```

生成周报：

```bash
python3 scripts/weekly_report.py generate \
  --report-dir /path/to/reports \
  --report-prefix student-weekly-report \
  --paper /tmp/weekly-paper.json \
  --literature /tmp/weekly-literature.json
```

自动选文献并生成周报：

```bash
python3 scripts/weekly_report.py generate \
  --report-dir /path/to/reports \
  --report-prefix student-weekly-report \
  --auto-paper
```

跳过渲染检查：

```bash
python3 scripts/weekly_report.py generate \
  --report-dir /path/to/reports \
  --report-prefix student-weekly-report \
  --auto-paper \
  --no-render
```

手动指定本周结束日期：

```bash
python3 scripts/weekly_report.py generate \
  --report-dir /path/to/reports \
  --report-prefix student-weekly-report \
  --week-ending 2026-07-19 \
  --auto-paper
```

## 文献精读 JSON

如果不使用自动草稿，可以手动准备文献精读 JSON：

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

然后传给 `generate`：

```bash
python3 scripts/weekly_report.py generate \
  --report-dir /path/to/reports \
  --report-prefix student-weekly-report \
  --literature /tmp/weekly-literature.json
```

## 文件命名

脚本会复制周报目录中日期最新的匹配前缀 `.docx` 作为模板。

例如：

```text
student-weekly-report-260712.docx
```

如果生成 2026-07-19 结束的周报，输出为：

```text
student-weekly-report-260719.docx
```

如果该文件已经存在，则输出：

```text
student-weekly-report-260719-v2.docx
```
