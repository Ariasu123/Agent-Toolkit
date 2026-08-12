---
name: webapp-testing
description: 使用 Playwright 与本地 web application 交互并测试的工具集；当需要验证前端功能、调试 UI 行为、截取浏览器截图或查看浏览器日志时调用。
---

# Web Application 测试

要测试本地 web application，编写原生 Python Playwright 脚本。

**可用辅助脚本**：
- `scripts/with_server.py` - 管理 server 生命周期（支持多个 server）

**始终先使用 `--help` 运行脚本**以查看用法。在首次尝试运行脚本并确认确实需要定制方案之前，不要阅读源码。这些脚本可能非常大，会污染上下文窗口。它们应作为黑盒脚本直接调用，而不是被加载到上下文窗口中。

## 决策树：选择你的方法

```
用户任务 → 是否为 static HTML？
    ├─ 是 → 直接读取 HTML 文件以识别 selector
    │         ├─ 成功 → 使用 selector 编写 Playwright 脚本
    │         └─ 失败/不完整 → 视为 dynamic（见下方）
    │
    └─ 否（dynamic webapp）→ server 是否已在运行？
        ├─ 否 → 运行：python scripts/with_server.py --help
        │        然后使用辅助脚本 + 编写简化的 Playwright 脚本
        │
        └─ 是 → 先侦察再行动：
            1. 导航并等待 networkidle
            2. 截图或检查 DOM
            3. 从渲染后的状态识别 selector
            4. 使用发现的 selector 执行操作
```

## 示例：使用 with_server.py

要启动 server，先运行 `--help`，然后使用辅助脚本：

**单个 server：**
```bash
python scripts/with_server.py --server "npm run dev" --port 5173 -- python your_automation.py
```

**多个 server（例如 backend + frontend）：**
```bash
python scripts/with_server.py \
  --server "cd backend && python server.py" --port 3000 \
  --server "cd frontend && npm run dev" --port 5173 \
  -- python your_automation.py
```

创建自动化脚本时，只包含 Playwright 逻辑（server 会自动管理）：
```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True) # 始终以 headless 模式启动 chromium
    page = browser.new_page()
    page.goto('http://localhost:5173') # server 已在运行并就绪
    page.wait_for_load_state('networkidle') # 关键：等待 JS 执行
    # ... 你的自动化逻辑
    browser.close()
```

## 先侦察再行动模式

1. **检查渲染后的 DOM**：
   ```python
   page.screenshot(path='/tmp/inspect.png', full_page=True)
   content = page.content()
   page.locator('button').all()
   ```

2. 从检查结果中**识别 selector**

3. 使用发现的 selector **执行操作**

## 常见陷阱

❌ **不要**在 dynamic app 上等待 `networkidle` 之前检查 DOM
✅ 在检查前等待 `page.wait_for_load_state('networkidle')`

## 最佳实践

- **将自带脚本作为黑盒使用** - 要完成任务时，先考虑 `scripts/` 中的某个脚本是否能提供帮助。这些脚本能可靠地处理常见复杂工作流，而不会塞满上下文窗口。使用 `--help` 查看用法，然后直接调用。
- 同步脚本使用 `sync_playwright()`
- 完成后始终关闭浏览器
- 使用描述性 selector：`text=`、`role=`、CSS selector 或 ID
- 添加适当的等待：`page.wait_for_selector()` 或 `page.wait_for_timeout()`

## 参考文件

- **examples/** - 展示常见模式的示例：
  - `element_discovery.py` - 发现页面上的 button、link 和 input
  - `static_html_automation.py` - 对本地 HTML 使用 file:// URL
  - `console_logging.py` - 在自动化过程中捕获 console log
