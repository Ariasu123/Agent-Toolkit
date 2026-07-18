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
