 📋 Git 工作流程

  日常开发（在 dev 分支）

  # 1. 确保在 dev 分支
  git checkout dev

  # 2. 拉取最新代码（如果团队协作）
  git pull origin dev

  # 3. 修改代码后提交
  git add .
  git commit -m "描述你的修改"
  git push origin dev

  合并到 main 分支

  当 dev 分支的功能开发完成并测试通过后：

  # 1. 切换到 main 分支
  git checkout main

  # 2. 拉取最新的 main（如果有其他人更新了）
  git pull origin main

  # 3. 合并 dev 分支到 main
  git merge dev

  # 4. 推送到 GitHub
  git push origin main

  ---
  🔍 当前分支结构

  * dev  (当前分支)  ← 你在这里开发
    └─ main         ← 稳定版本

  两个分支目前内容相同（都在同一个 commit: ddd225b）

我来详细解释 .gitignore 中每个部分为什么要被忽略：

  1. Python 编译文件

  __pycache__/
  *.py[cod]
  *.so
  原因：Python 运行时会自动生成这些文件，包括：
  - __pycache__ 存放 .pyc 字节码文件，加速下次运行
  - 每个开发者环境不同，不需要共享
  - 可以通过 *.py 源码重新生成

  2. 虚拟环境

  .venv/
  venv/
  ENV/
  原因：
  - 虚拟环境包含安装的依赖包，体积大（几百MB）
  - 每个开发者需要独立创建虚拟环境
  - 通过 pyproject.toml 或 requirements.txt 就能重建环境
  - 不同操作系统/Mac/Windows 的环境不兼容

  3. UV 锁文件

  uv.lock
  原因：
  - UV 是 Python 新的包管理工具
  - uv.lock 包含平台特定的依赖版本（Windows/Mac/Linux 不同）
  - 应该让每个环境用自己的 lock 文件
  - pyproject.toml 已经定义了依赖版本范围

  4. IDE 配置

  .vscode/
  .idea/
  *.swp
  原因：
  - VSCode/PyCharm 的个人配置（主题、插件、代码格式规则）
  - 每个开发者有自己的 IDE 偏好
  - 不应该强制团队使用相同的 IDE 设置

  5. 日志文件

  logs/
  *.log
  原因：
  - 日志文件会不断增长，占用大量空间
  - 包含运行时信息、错误栈，不应该提交到代码库
  - 生产环境的日志可能包含敏感信息
  - 每次运行都会生成新的日志

  6. 环境变量

  .env
  .env.local
  原因：
  - 安全风险：包含数据库密码、API 密钥等敏感信息
  - 每个部署环境不同（开发/测试/生产）
  - 提交到 GitHub 会被公开访问，导致密钥泄露
  - 应该提供 .env.example 模板供他人参考

  7. 模型大文件

  pytorch_model.bin
  *.safetensors
  *.bin
  原因：
  - embedding 模型文件通常几百MB到几GB
  - 你的项目有 bge-large-zh-v1.5/pytorch_model.bin，可能超过 1GB
  - GitHub 单文件限制 100MB
  - 应该使用 Git LFS 或放在云存储
  - 运行时可以自动下载模型

  8. 系统文件

  .DS_Store
  Thumbs.db
  原因：
  - macOS 的 .DS_Store 存储文件夹显示设置
  - Windows 的 Thumbs.db 存储缩略图缓存
  - 与项目代码无关，只是系统自动生成的

  9. 测试和覆盖率

  .pytest_cache/
  .coverage
  htmlcov/
  原因：
  - 测试运行生成的临时文件和覆盖率报告
  - 每次运行都会更新，不需要提交
  - CI/CD 环境会重新生成

  10. 构建产物

  build/
  dist/
  *.egg-info/
  原因：
  - Python 包安装/打包生成的文件
  - 可以从源码重新构建
  - 包含平台特定的二进制文件

  ---
  核心原则

  应该提交：源代码、配置文件模板、文档、pyproject.toml

  不应该提交：
  - 可以自动生成的文件（__pycache__）
  - 体积巨大的文件（模型、虚拟环境）
  - 包含敏感信息的文件（.env）
  - 个人/系统特定的文件（IDE配置、系统缓存）

  这样可以保持代码库干净、安全、体积小，并且便于团队协作


 非常好的问题！确实可以用 conda(know) 安装依赖，但有几个重要区别：

  为什么用项目专属环境而不是共享 conda 环境：

  1. 项目隔离（最重要）
    - ❌ conda(know) 是共享环境 - 你其他项目也用这个环境，依赖会混在一起
    - ✅ .venv 是项目专属 - 只给 data-agent 用，干净独立
    - 问题：如果你有 3 个项目，每个需要不同版本的 langchain，conda 环境会冲突
  2. 团队协作 - 版本一致性
    - ✅ uv 使用 pyproject.toml 和 uv.lock - 锁定精确版本
    - ❌ conda 手动安装 - 可能大家装的版本不一样
    - 场景：你的同事张三用 langchain==1.2.7，你装成了 1.3.0，代码可能报错
  3. 可复现性
    - ✅ 新同事来，只需要：git clone → uv sync → 完成（2分钟）
    - ❌ 用 conda：手动 pip install 一大堆包，容易漏装或版本冲突
  4. uv 的优势
    - ⚡ 安装速度快很多（刚才你看到了，30多秒装了109个包）
    - 🔒 更好的依赖冲突解决
    - 📦 pyproject.toml 是项目配置文件的一部分，会提交到 git

  总结：
  - 个人练习项目 → 用 conda 环境也行
  - 团队协作/生产项目 → 用项目专属环境（uv 的 .venv）