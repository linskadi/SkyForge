# SkyForge 比赛提交同步指南（AtomGit）

> 本文档用于指导「航空工业软件开源创新大赛 · 机上软件开发工具赛道」开源交付物在 AtomGit 上的同步与发布。
>
> **重要安全约束**：`git push` 需由维护者确认，或由自动化任务在获得明确授权后执行。请逐项核对后再操作。

---

## 一、AtomGit 仓库初始化

### 1. 网页端创建公开仓库

```text
# 1. 登录 AtomGit (https://atomgit.com)
# 2. 确认 AtomGit 上 SkyForge 公开仓库可访问
#    仓库地址: https://atomgit.com/gcw_TTqe9ALQ/SkyForge
# 3. 仓库属性必须选择「公开项目」(严禁私有)
# 4. 添加全体队员 AtomGit 用户名至协作人列表(读写权限)
# 5. GitHub 镜像地址: https://github.com/linskadi/SkyForge
```

### 2. 本地代码同步(用户手动执行)

```bash
# 进入 SkyForge 项目根目录
cd c:/Users/Lin/Desktop/Programs/Air/SkyForge

# 检查当前 git 状态(查看是否有未提交的更改)
git status

# 如果有未提交的更改,先提交
git add .
git commit -m "feat: 完成 SkyForge 比赛优化任务(Task 1-11)

- Task 1: 项目根目录整洁化
- Task 2: docs/ 目录重组与文档分类
- Task 3: README.md 重写
- Task 4: 性能基准测试套件创建
- Task 5: 形式化验证演示集成(CLI/API/前端)
- Task 6: 竞品对比分析深化
- Task 7: 量化效率数据补充
- Task 8: 产业应用案例扩充
- Task 9: 航空运行时场景示例扩充(ARINC 653 + FreeRTOS)
- Task 10: ARINC 653 适配器增强
- Task 11: 提交包准备与最终检查

测试状态: uv run pytest -q 596 passed；pnpm test 172 passed；pnpm test:e2e 4 passed"

# 添加远程仓库
git remote add atomgit https://atomgit.com/gcw_TTqe9ALQ/SkyForge.git
# (如果已存在,使用以下命令更新地址)
git remote set-url atomgit https://atomgit.com/gcw_TTqe9ALQ/SkyForge.git
git remote set-url origin https://github.com/linskadi/SkyForge.git

# 确认远程地址
git remote -v

# 推送代码（维护者确认或授权自动化后执行）
git push atomgit main
git push origin main
```

> **说明**：当前本地远端名约定为 `atomgit`（AtomGit）与 `origin`（GitHub）。

---

## 二、重要提示(必读)

1. **仓库必须为公开项目**，严禁私有。比赛要求开源交付，私有仓库视为不符合要求。
2. **添加所有团队成员为协作者**（读写权限），便于后续协作与代码评审。
3. 推送前确认 `LICENSE` 文件存在且为 **MIT License**（位于 `SkyForge/LICENSE`）。
4. 推送前确认 `ThirdParty.md` 完整标注所有第三方组件来源、版本、引用说明；补充材料位于 `docs/thirdparty/`。
5. **严禁删除代码、移除 LICENSE**。必须上传完整代码，缺失核心内容视为不符合开源交付要求。
6. 推送前建议本地运行 `make test`、`make do178c-check`、`make benchmark`，确认无误后再推送。
7. 推送完成后，在 AtomGit 网页确认仓库可见性为「公开」，否则评委无法访问。
8. 大文件（如 `node_modules/`、`.venv/`、`dist/`、`__pycache__/`、`output/`）已在 `.gitignore` 中排除，请勿手动提交。

---

## 三、验证清单(用户推送后自查)

请在推送完成后逐项确认：

- [ ] 仓库地址正确（`atomgit.com/gcw_TTqe9ALQ/SkyForge` 与 `github.com/linskadi/SkyForge`）
- [ ] 仓库为**公开**状态（网页右上角可见「Public」标识）
- [ ] `LICENSE` 文件存在且为 MIT
- [ ] `ThirdParty.md` 完整，`docs/thirdparty/` 补充材料可访问
- [ ] `README.md` 可读，包含项目说明、架构图、快速开始
- [ ] `src/` 目录存在且包含核心代码（四层架构：`skyforge_core` / `skyforge_engine` / `skyforge_llm` / `studio`）
- [ ] `docs/` 目录包含当前统一文档（USER_GUIDE / DO178C_COMPLIANCE_PACKAGE / PROJECT_REVIEW / COMPETITION_EDITION / benchmark / verification / images）
- [ ] DO-178C 计划与 DO-330 工具鉴定草案已合并到 `docs/DO178C_COMPLIANCE_PACKAGE.md`
- [ ] `examples/` 目录存在（12 个基础示例 + 2 个完整示例：ARINC 653 + FreeRTOS）
- [ ] 已添加全体团队成员为协作者
- [ ] 分支为 `main`（或 `master`）且为默认分支

---

## 四、相关文件位置

| 交付物 | 路径 |
|--------|------|
| 源代码包 | `c:\Users\Lin\Desktop\Programs\Air\SkyForge-source.zip` |
| 提交邮件模板 | `c:\Users\Lin\Desktop\Programs\Air\competition\SUBMISSION_EMAIL.txt` |
| 最终验证清单 | `c:\Users\Lin\Desktop\Programs\Air\competition\FINAL_CHECKLIST.md` |
| 本同步指南 | `SkyForge/docs/SUBMISSION_GUIDE.md` |

---

## 五、时间节点提醒

- **开源交付截止**：2026 年 7 月 20 日
- **收件邮箱**：kefu@jsopen.org.cn
- **邮件标题格式**：`【航空工业软件开源创新大赛报名】+选题+团队名称`
  - 示例：`【航空工业软件开源创新大赛报名】机上软件开发工具赛道+SkyForge 团队`

> 请在截止日期前完成：① 推送代码到 AtomGit 公开仓库；② 发送提交邮件（附件含 `SkyForge-source.zip`）。

---

**文档生成日期**：2026-07-17
**生成者**：SkyForge 比赛优化自动化任务（Task 11）
