# course-paper-writing

状态：**0.5.0-draft**。根据实际使用反馈更新；新版网页端成文与 Codex 核验的完整链路
仍待实战验证，不宣称已验证节省具体 token 数。

用于课程小论文的调研、评论、驳论与综述，通常 2000–5000 字，实际服从课程篇幅。
输入“选题 + 要求”；已有进展则带上材料，从未完成位置继续。

1. **立意**：用户选定方向并表达自己的判断（Gate 1）。
2. **资料与阅读**：按主题选库，分类整理独立阅读摘要、定位与空缺（Gate 2）。
3. **网页端讨论与成文**：Codex 准备 prompt，用户手动上传阅读摘要；网页端采集观点/风格，
   生成 return 初版并自检，集中确认最后结构和格式（Gate 3），随即生成论文并更新 return。
4. **Codex 核验校准**：用户回传论文和最新 return；核实际引用、篇幅及格式，必要局部修改
   或转换排版，由用户审阅确认（Gate 4）。Codex 默认不重新生成全文。

```text
$course-paper-writing
课程与题型：课程评论论文
篇幅与原始格式要求：附教师通知
选题：校内共享单车管理
已有材料：reading-digest.md
请从 Stage 3 准备网页端 prompt 开始。
```

关键观点来自用户真实讨论，不强制先交四段亲笔稿；样本、真实原稿与 AI 新稿分开。
保留原话和原稿，按授权改动。如实记录阅读范围、来源版本与本轮核验，
不把作者 abstract、OCR 或继承笔记冒充亲自完成的全文阅读。

教师原文、用户追加和排版建议分开；摘要是否计字数、是否需要英文摘要、
页下注及文后参考文献均按实际要求核对。不承诺 AI 检测结果。

入口：[SKILL.md](SKILL.md)。Stage 3 资源：[网页 prompt](templates/web-llm-prompt.md)、
[return](templates/web-llm-return.md)；Stage 4：[核验单](templates/submission-check.md)。
模拟场景：[首次立意](examples/stage-1-demo.md)、[往返验收场景](examples/roundtrip-scenarios.md)。

`paper-search` 是可选检索工具，返回元数据线索；阅读摘要和全文核验由写作流程负责。
项目原稿和状态放在用户自己的目录；安装方式见
[仓库 README](https://github.com/Breeze-aura/skills#readme)。
