# Learn Pi Web 阅读器

这是 `learn-pi` 的课程阅读器，使用 Next.js App Router。

## 真源

页面服务端直接读取上一级目录的：

- `course.json`：系统和章节导航。
- `sNN_*/README.md`：章节正文。
- `sNN_*/architecture.svg`：章节架构图。
- `UPSTREAM.md`：源码证据页。

Web 不复制章节正文，也不读取参考项目的 `docs/` 旧版内容。

## 运行

从仓库根目录执行：

```powershell
npm --prefix learn-pi/web install
npm --prefix learn-pi/web run dev
```

打开 `http://localhost:3000`。生产构建：

```powershell
npm --prefix learn-pi/web run typecheck
npm --prefix learn-pi/web run build
```

可用环境变量 `LEARN_PI_ROOT` 指定课程真源目录，默认是 Web 目录的上一级 `learn-pi`。
