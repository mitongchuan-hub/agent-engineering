"use client";

import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  Check,
  CheckCircle2,
  ChevronDown,
  ExternalLink,
  FileCode2,
  GitBranch,
  Menu,
  Search,
  X,
} from "lucide-react";
import Link from "next/link";
import { useMemo, useState, type ReactNode } from "react";

import type { CourseChapter, CourseData } from "../lib/course";

interface ReaderShellProps {
  course: CourseData;
  activeChapter?: CourseChapter;
  markdownHtml: string;
  architectureSvg?: string;
  sourcePage?: boolean;
  children?: ReactNode;
}

function statusText(status: CourseChapter["status"]): string {
  if (status === "completed") return "已完成";
  if (status === "in-progress") return "进行中";
  return "计划中";
}

export function ReaderShell({
  course,
  activeChapter,
  markdownHtml,
  architectureSvg,
  sourcePage = false,
}: ReaderShellProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [query, setQuery] = useState("");
  const normalizedQuery = query.trim().toLowerCase();

  const visibleSystems = useMemo(
    () =>
      course.systems
        .map((system) => ({
          system,
          chapters: system.chapters
            .map((id) => course.chapters.find((chapter) => chapter.id === id))
            .filter((chapter): chapter is CourseChapter => Boolean(chapter))
            .filter((chapter) => {
              if (!normalizedQuery) return true;
              return `${chapter.id} ${chapter.title}`.toLowerCase().includes(normalizedQuery);
            }),
        }))
        .filter(({ chapters }) => chapters.length > 0),
    [course, normalizedQuery],
  );

  const activeIndex = activeChapter
    ? course.chapters.findIndex((chapter) => chapter.id === activeChapter.id)
    : -1;
  const previous = activeIndex > 0 ? course.chapters[activeIndex - 1] : undefined;
  const next = activeIndex >= 0 && activeIndex < course.chapters.length - 1 ? course.chapters[activeIndex + 1] : undefined;
  const activeSystem = activeChapter
    ? course.systems.find((system) => system.id === activeChapter.system)
    : undefined;

  function closeSidebar() {
    setSidebarOpen(false);
  }

  return (
    <div className="reader-shell">
      <button
        className="mobile-menu-button"
        type="button"
        aria-label={sidebarOpen ? "关闭课程目录" : "打开课程目录"}
        title={sidebarOpen ? "关闭课程目录" : "打开课程目录"}
        onClick={() => setSidebarOpen((open) => !open)}
      >
        {sidebarOpen ? <X size={19} /> : <Menu size={19} />}
        <span>目录</span>
      </button>

      <aside className={`course-sidebar${sidebarOpen ? " is-open" : ""}`}>
        <div className="sidebar-brand">
          <div className="brand-mark"><BookOpen size={17} /></div>
          <div>
            <div className="brand-name">LEARN PI</div>
            <div className="brand-subtitle">Coding Agent 源码课程</div>
          </div>
        </div>

        <div className="sidebar-scope">
          <div className="scope-label">当前课程</div>
          <div className="scope-title">{course.title}</div>
          <div className="scope-commit"><GitBranch size={13} /> {course.upstream.commit.slice(0, 8)}</div>
        </div>

        <label className="search-field">
          <Search size={16} />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="搜索章节"
            aria-label="搜索章节"
          />
          {query && (
            <button type="button" aria-label="清除搜索" title="清除搜索" onClick={() => setQuery("")}>
              <X size={14} />
            </button>
          )}
        </label>

        <nav className="course-nav" aria-label="课程章节">
          {visibleSystems.map(({ system, chapters }, systemIndex) => (
            <section className="nav-system" key={system.id}>
              <div className="nav-system-heading">
                <span className="system-number">{String(systemIndex + 1).padStart(2, "0")}</span>
                <span>{system.title}</span>
                <ChevronDown size={14} />
              </div>
              <div className="nav-chapters">
                {chapters.map((chapter) => {
                  const chapterIndex = course.chapters.findIndex((item) => item.id === chapter.id);
                  const isActive = activeChapter?.id === chapter.id;
                  return (
                    <Link
                      key={chapter.id}
                      href={`/${chapter.id}`}
                      className={`nav-chapter${isActive ? " is-active" : ""}`}
                      aria-current={isActive ? "page" : undefined}
                      onClick={closeSidebar}
                    >
                      <span className="chapter-index">{String(chapterIndex + 1).padStart(2, "0")}</span>
                      <span className="chapter-link-title">{chapter.title}</span>
                      {chapter.status === "completed" && <Check size={14} className="chapter-check" />}
                    </Link>
                  );
                })}
              </div>
            </section>
          ))}
          {visibleSystems.length === 0 && <div className="empty-search">没有匹配章节</div>}
        </nav>

        <div className="sidebar-footer">
          <Link href="/sources" className={`evidence-link${sourcePage ? " is-active" : ""}`} onClick={closeSidebar}>
            <FileCode2 size={16} />
            <span>源码证据</span>
            <ExternalLink size={13} />
          </Link>
          <div className="offline-note"><span className="status-dot" /> 默认离线实验</div>
        </div>
      </aside>

      {sidebarOpen && <button className="sidebar-backdrop" type="button" aria-label="关闭课程目录" onClick={closeSidebar} />}

      <main className="reader-main">
        <header className="reader-topbar">
          <div className="breadcrumb">
            <span>LEARN PI</span>
            <span className="breadcrumb-divider">/</span>
            <span>{sourcePage ? "源码证据" : activeSystem?.title ?? "课程"}</span>
            {!sourcePage && activeChapter && <><span className="breadcrumb-divider">/</span><span>{activeChapter.id}</span></>}
          </div>
          <a className="upstream-link" href={course.upstream.repository} target="_blank" rel="noreferrer">
            <GitBranch size={15} /> 上游仓库 <ExternalLink size={13} />
          </a>
        </header>

        <div className="reader-content">
          <header className="chapter-header">
            <div className="chapter-kicker">
              <span>{sourcePage ? "SOURCE / UPSTREAM" : `CHAPTER ${activeChapter ? String(activeIndex + 1).padStart(2, "0") : "--"}`}</span>
              <span className="kicker-line" />
              <span>{sourcePage ? course.upstream.commit.slice(0, 12) : activeSystem?.title}</span>
            </div>
            <h1>{sourcePage ? "Pi 源码证据" : activeChapter?.title}</h1>
            <div className="chapter-facts">
              {!sourcePage && activeChapter && (
                <span className="fact fact-complete"><CheckCircle2 size={15} /> {statusText(activeChapter.status)}</span>
              )}
              <span className="fact"><GitBranch size={15} /> {course.upstream.commit.slice(0, 8)}</span>
              <span className="fact"><FileCode2 size={15} /> TypeScript → Python</span>
            </div>
          </header>

          {!sourcePage && architectureSvg && (
            <figure className="architecture-panel">
              <div className="section-label"><span>ARCHITECTURE</span><span>源码机制图</span></div>
              <div className="architecture-art" dangerouslySetInnerHTML={{ __html: architectureSvg }} />
            </figure>
          )}

          <article className="reader-article" dangerouslySetInnerHTML={{ __html: markdownHtml }} />

          {!sourcePage && (previous || next) && (
            <nav className="chapter-pager" aria-label="章节导航">
              {previous ? (
                <Link href={`/${previous.id}`} className="pager-link pager-prev">
                  <ArrowLeft size={17} />
                  <span><small>上一章</small><strong>{previous.title}</strong></span>
                </Link>
              ) : <span />}
              {next ? (
                <Link href={`/${next.id}`} className="pager-link pager-next">
                  <span><small>下一章</small><strong>{next.title}</strong></span>
                  <ArrowRight size={17} />
                </Link>
              ) : <span />}
            </nav>
          )}
        </div>
      </main>
    </div>
  );
}
