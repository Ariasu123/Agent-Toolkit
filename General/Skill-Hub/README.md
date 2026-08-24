# Skill-Hub

优秀开源 Agent Skills 精选收录。每个 skill 为一个独立目录，内含 `SKILL.md` 及配套脚本/资源。

## 收录清单

| Skill | 功能 | 上游 | 许可证 |
|---|---|---|---|
| **webapp-testing** | 用 Playwright 测试本地 web 应用：自动起服务、截图、读取日志、验证交互。 | [anthropics/skills](https://github.com/anthropics/skills) | Apache-2.0 |
| **code-simplifier** | 在保持功能不变的前提下，简化最近修改过的代码，遵循项目自身规范。 | [anthropics/skills](https://github.com/anthropics/skills) | Apache-2.0 |
| **frontend-design** | 生成高品质前端界面，内置"避免 AI 廉价审美"的设计准则。 | [anthropics/skills](https://github.com/anthropics/skills) | Apache-2.0 |
| **mcp-builder** | 构建高质量 MCP server 的完整指南，覆盖 Python（FastMCP）与 Node SDK，含评估脚本。 | [anthropics/skills](https://github.com/anthropics/skills) | Apache-2.0 |
| **skill-creator** | 元工具：创建、打包、评测 skill，含 eval 运行与 description 优化脚本。 | [anthropics/skills](https://github.com/anthropics/skills) | Apache-2.0 |
| **doc-coauthoring** | 三阶段协同写文档工作流：上下文收集 → 内容精炼 → 读者测试。 | [anthropics/skills](https://github.com/anthropics/skills) | Apache-2.0 |
| **smart-web-scraper** | 基于 Playwright 的反爬网页抓取，可绕过 Cloudflare 等防护，输出文本 + 截图。 | [waisimon/playwright-scraper-skill](https://github.com/waisimon/playwright-scraper-skill) | MIT（作者 Simon Chan） |
| **firecrawl-cli** | 通过 Firecrawl CLI 搜索、抓取网页并与页面交互，返回适配 LLM 上下文的干净 markdown。 | [firecrawl/cli](https://github.com/firecrawl/cli) | ISC |
| **firecrawl-parse** | 把本地文件（PDF/DOCX/XLSX/HTML 等）解析为干净的 markdown 落盘。 | [firecrawl/cli](https://github.com/firecrawl/cli) | ISC |

## 说明

- 各 skill 的内容与其上游仓库保持一致，未做功能修改；如有更新请回溯上游。
- 再分发时请保留对应上游的许可证与署名要求。
