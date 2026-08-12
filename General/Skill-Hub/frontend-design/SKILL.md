---
name: frontend-design
description: 打造具有高品质设计的独特且生产级的前端界面。当用户要求构建 web 组件、页面、作品、海报或应用（例如网站、落地页、仪表盘、React 组件、HTML/CSS 布局，或对任何 web UI 进行样式美化/美化）时触发。生成富有创意且精致的代码与 UI 设计，避免通用 AI 审美。
---

本 Skill 用于指导创建独特、生产级的前端界面，避免通用“AI 廉价审美”。编写真正可运行的代码，特别关注美学细节与创意选择。

用户提供前端需求：要构建的 component、page、application 或 interface。可能包含用途、受众或技术约束等上下文。

## Design Thinking

开始编码前，先理解上下文并确定一个大胆的审美方向：
- **Purpose**：该 interface 解决什么问题？谁使用它？
- **Tone**：选择一个极端方向：brutally minimal、maximalist chaos、retro-futuristic、organic/natural、luxury/refined、playful/toy-like、editorial/magazine、brutalist/raw、art deco/geometric、soft/pastel、industrial/utilitarian 等。可从中汲取灵感，但设计必须忠于所选审美方向。
- **Constraints**：技术要求（framework、performance、accessibility）。
- **Differentiation**：什么让它令人难忘？哪个点是用户会记住的？

**关键**：选择清晰的概念方向并精确执行。大胆 maximalism 与精致 minimalism 都可行，关键是意图明确，而非强度。

然后实现可运行的代码（HTML/CSS/JS、React、Vue 等），并确保其：
- 生产级且功能完整
- 视觉冲击力强且令人难忘
- 具有明确审美观点的一致性
- 每个细节都经过精心打磨

## Frontend Aesthetics Guidelines

重点关注：
- **Typography**：选择美观、独特且有趣的 font。避免 Arial、Inter 等通用 font；选择能提升 frontend 美感的特色字体，出人意料且富有个性。将一款特色 display font 与精致 body font 搭配使用。
- **Color & Theme**：坚持统一的审美。使用 CSS variables 保持一致性。主色搭配锐利强调色，优于保守且平均分布的 palette。
- **Motion**：使用 animations 实现效果与 micro-interactions。HTML 优先使用纯 CSS 方案。React 中可用 Motion library。聚焦高影响力时刻：一次编排良好的页面加载配合 staggered reveals（animation-delay）比零散的 micro-interactions 更能带来愉悦。使用能带来惊喜的 scroll-triggering 与 hover states。
- **Spatial Composition**：出人意料的布局。Asymmetry。Overlap。Diagonal flow。Grid-breaking elements。大量 negative space，或是有控制的密度。
- **Backgrounds & Visual Details**：营造氛围与深度，而非默认纯色。添加与整体审美相符的 contextual effects 与 textures。使用 gradient meshes、noise textures、geometric patterns、layered transparencies、dramatic shadows、decorative borders、custom cursors、grain overlays 等创意形式。

严禁使用通用 AI 生成审美，例如滥用的 font family（Inter、Roboto、Arial、system fonts）、cliché color scheme（尤其是白底紫色渐变）、可预测的布局与 component patterns，以及缺乏上下文特色的模板化设计。

发挥创意进行诠释，做出出人意料、真正为当前上下文量身定制的选择。每次设计都不应雷同。在 light/dark themes、不同 fonts、不同 aesthetics 之间变化。切勿跨代收敛到常见选择（例如 Space Grotesk）。

**重要**：实现复杂度需与审美愿景匹配。Maximalist 设计需要复杂代码、大量 animations 与 effects。Minimalist 或 refined 设计需要克制、精确，并仔细关注 spacing、typography 与 subtle details。优雅来自对愿景的出色执行。

记住：你有能力完成非凡的创意工作。不要保守，尽情展示跳出框架、全情投入独特愿景后真正能创造出的作品。
