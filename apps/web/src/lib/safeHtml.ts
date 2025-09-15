// Very basic allowlist sanitizer that keeps <b> tags and escapes others.
// This is not a complete sanitizer; backend should ensure safety.
export function sanitizeSnippet(html: string): string {
  // Remove script/style and their content
  let out = html.replace(/<\/(script|style)>/gi, '')
    .replace(/<(script|style)[^>]*>[\s\S]*?<\/\1>/gi, '');
  // Escape all tags except <b>
  out = out
    .replace(/<(?!(\/?b(?=>|\s)))[^>]+>/gi, (match) => escapeHtml(match))
    .replace(/&lt;(\/?)b(.*?)&gt;/gi, '<$1b$2>');
  return out;
}

export function escapeHtml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// Convert simple markdown-like answer to HTML with bold (**bold**), paragraphs, and line breaks.
export function answerTextToHtml(text: string): string {
  const escaped = escapeHtml(text);
  // Bold: **text** -> <strong>text</strong>
  const withBold = escaped.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  // Paragraphs: split by double newlines
  const blocks = withBold.split(/\n\n+/).map((b) => b.replace(/\n/g, '<br/>'));
  return blocks.map((b) => `<p>${b}</p>`).join('');
}
