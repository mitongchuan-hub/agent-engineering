import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { unified } from "unified";
import rehypeHighlight from "rehype-highlight";
import rehypeRaw from "rehype-raw";
import rehypeStringify from "rehype-stringify";
import remarkGfm from "remark-gfm";
import remarkParse from "remark-parse";
import remarkRehype from "remark-rehype";

export type Status = "completed" | "in-progress" | "planned";

export interface CourseSystem {
  id: string;
  title: string;
  chapters: string[];
  status: Status;
}

export interface CourseChapter {
  id: string;
  title: string;
  system: string;
  status: Status;
  path: string;
  topics?: string[];
  sources?: string[];
}

export interface CourseData {
  id: string;
  title: string;
  language: string;
  upstream: {
    repository: string;
    commit: string;
    localPath: string;
  };
  course: {
    focus: string;
    offlineByDefault: boolean;
    sharedEnvironment: string;
    systemsDocument: string;
    note: string;
  };
  systems: CourseSystem[];
  chapters: CourseChapter[];
}

function courseRoot(): string {
  return resolve(process.env.LEARN_PI_ROOT ?? resolve(process.cwd(), ".."));
}

async function readCourseFile(relativePath: string): Promise<string> {
  return readFile(resolve(courseRoot(), relativePath), "utf8");
}

export async function getCourse(): Promise<CourseData> {
  return JSON.parse(await readCourseFile("course.json")) as CourseData;
}

export async function getChapterContent(chapter: CourseChapter): Promise<{
  markdown: string;
  architecture: string;
}> {
  const [markdown, architecture] = await Promise.all([
    readCourseFile(`${chapter.path}/README.md`),
    readCourseFile(`${chapter.path}/architecture.svg`),
  ]);
  return { markdown, architecture };
}

export async function getUpstreamContent(): Promise<string> {
  return readCourseFile("UPSTREAM.md");
}

export async function renderMarkdown(markdown: string): Promise<string> {
  const rendered = await unified()
    .use(remarkParse)
    .use(remarkGfm)
    .use(remarkRehype, { allowDangerousHtml: true })
    .use(rehypeRaw)
    .use(rehypeHighlight)
    .use(rehypeStringify)
    .process(markdown);

  // README 内的本地证据链接统一指向阅读器的证据页。
  return String(rendered).replace(/href="\.\.\/UPSTREAM\.md"/g, 'href="/sources"');
}

export function chapterNumber(course: CourseData, chapterId: string): string {
  const index = course.chapters.findIndex((chapter) => chapter.id === chapterId);
  return String(index + 1).padStart(2, "0");
}
