import { ReaderShell } from "../../components/reader-shell";
import { getCourse, getUpstreamContent, renderMarkdown } from "../../lib/course";

export const metadata = {
  title: "Pi 源码证据 | Learn Pi",
};

export default async function SourcesPage() {
  const [course, upstream] = await Promise.all([getCourse(), getUpstreamContent()]);
  const markdownHtml = await renderMarkdown(upstream);
  return <ReaderShell course={course} markdownHtml={markdownHtml} sourcePage />;
}
