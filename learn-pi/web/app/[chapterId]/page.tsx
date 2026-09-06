import { notFound } from "next/navigation";

import { ReaderShell } from "../../components/reader-shell";
import { getChapterContent, getCourse, renderMarkdown, type CourseChapter } from "../../lib/course";

export async function generateStaticParams() {
  const course = await getCourse();
  return course.chapters.map((chapter) => ({ chapterId: chapter.id }));
}

export async function generateMetadata({ params }: { params: Promise<{ chapterId: string }> }) {
  const { chapterId } = await params;
  const course = await getCourse();
  const chapter = course.chapters.find((item) => item.id === chapterId);
  return chapter
    ? { title: `${chapter.title} | Learn Pi` }
    : { title: "Learn Pi" };
}

export default async function ChapterPage({ params }: { params: Promise<{ chapterId: string }> }) {
  const { chapterId } = await params;
  const course = await getCourse();
  const chapter: CourseChapter | undefined = course.chapters.find((item) => item.id === chapterId);
  if (!chapter) notFound();

  const content = await getChapterContent(chapter);
  const markdownHtml = await renderMarkdown(content.markdown);

  return (
    <ReaderShell
      course={course}
      activeChapter={chapter}
      markdownHtml={markdownHtml}
      architectureSvg={content.architecture}
    />
  );
}
