# Personal Skills & Prompts

个人 **skills 与 prompts** 开源仓库。围绕学业、科研、竞赛与实际工作，
把反复使用的方法沉淀成可复用、可验证的工具。

当前首要工程是课程小论文写作；仓库会随实际需求持续扩展。

## 当前内容

| 内容 | 用途 | 状态 |
| --- | --- | --- |
| [course-paper-writing](skills/course-paper-writing/README.md) | 课程论文：立意、独立阅读、网页端成文、Codex 核验校准 | 0.5.0-draft |
| [论文启动 prompt](prompts/course-paper-start.md) | 用选题与要求开始或恢复项目 | 可复制使用 |
| [paper-search](skills/paper-search/README.md) | 学术元数据检索、项目待读清单与写作资料交接 | 0.2.0-draft |

课程写作已依据实际使用反馈修订；`paper-search` 从云端迁入并修订。
新版流程将论文生成放在网页端，Codex 接收论文与 return 后核验校准。
模拟示例只说明交互和验收要求，完整新版链路仍待实战验证。

## 在 Codex 中全局使用

克隆仓库后，在仓库根目录运行：

```powershell
python -m pip install -r requirements-dev.txt
python tools/sync_skills.py
```

工具把 `skills/` 下的 skill 链接到 `~/.agents/skills/`，默认允许 Codex
按任务选择 skill；也可以在对话里明确调用：

```text
$course-paper-writing
我需要写一篇2000字的新中国史课程评论论文，主题是深圳经济特区与邓小平同志。
```

全局路径与目录链接支持依据
[Codex 官方文档](https://learn.chatgpt.com/docs/build-skills)。若新 skill 未出现，重启 Codex。

Windows 使用 junction，其他系统使用 symlink。仓库中的修改会通过链接直接反映，
无需重复复制；新增 skill 后再次运行同步工具。不要移动或删除被链接的源目录。
工具遇到同名的其他安装会报错，保留原内容；不会覆盖、镜像删除或修改第三方 skills。

```powershell
# 查看将安装的内容
python tools/sync_skills.py --dry-run

# 只安装一个 skill
python tools/sync_skills.py --skill course-paper-writing

# 安装到另一位置
python tools/sync_skills.py --destination "C:/path/to/skills"
```

不使用链接时，也可以手工把单个完整 skill 文件夹复制到全局目录，
后续自行更新；同步工具会保留这种已有副本并报告同名冲突。

## 结构与维护

```text
skills/      独立 skills，SKILL.md 是入口
prompts/     短提示词
tools/       校验与全局同步工具
tests/       工具行为测试
docs/        设计、实施与行为验证说明
local/       真实项目材料（本地创建，Git 忽略）
```

真实论文与原稿放在具体项目中，本仓库可使用 `local/`。
公开例子需要是模拟数据，或经过本人对具体公开内容的确认。
本地 `SKILLS-HANDOFF.md` 保留为交接材料，默认不进入公开仓库。

安装验证依赖后运行：

```powershell
python -m pip install -r requirements-dev.txt
python tools/validate_skills.py
python -m unittest discover -s tests -v
```

同步与结构校验使用 PyYAML 解析清单，避免把损坏 YAML 安装到全局目录。
CI 在 Windows 与 Linux 上运行相同检查。结构校验不能代替真实任务验证，
行为测试与局限见 [docs/evaluation.md](docs/evaluation.md)。

每个新 skill 使用小写短横线名称，保持目录名与 frontmatter `name` 一致，
只收录确有用途的说明、资源与脚本。先在实际任务里检验，再据此修订。

设计见 [docs/design.md](docs/design.md)，后续工程见 [Roadmap](ROADMAP.md)。
许可：[MIT](LICENSE)。
