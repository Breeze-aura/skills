# paper-search

0.2.0-draft。先按主题匹配合适的文献库；中文主题优先中文文献，科研主题优先专业期刊与专业文献库。
脚本提供 Semantic Scholar 学术元数据检索与 arXiv 预印本兜底，
支持年份范围、候选排序、结构化 JSON 和项目待读清单。

本 skill 不代替全文阅读、系统综述或论文写作。入口见 [SKILL.md](SKILL.md)，
写作衔接见 [交接规则](references/writing-handoff.md)。

脚本仅用 Python 标准库。安装后的调用使用 script 的绝对路径，并保持工作目录
在自己的项目中。UI 允许按任务语义自动选用，也可显式调用 `$paper-search`。

```text
python "<skill目录>/scripts/search_papers.py" --query "EEG microstate review" --limit 8 --year-from 2020 --format json
```

保存清单时增加 `--save --save-path "<项目目录>/reading_list.md"`。
检索日期、数据来源、年份口径与阅读状态保留在交接记录中。

服务失败时停止并报告；中文历史等问题应补充合适的原始资料，不能靠 arXiv 凑数。
