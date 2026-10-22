// Run by verify_clean_db.py with frontend/ as the working directory (so the packages resolve).
// Reads {key, md, expected, structure} lines and parses each md the way the frontend renders it.
import { readFileSync } from "node:fs";
import { unified } from "unified";
import remarkParse from "remark-parse";
import remarkGfm from "remark-gfm";
import { toString } from "mdast-util-to-string";

const lines = readFileSync(process.argv.at(-1), "utf8").split("\n").filter(Boolean);
const processor = unified().use(remarkParse).use(remarkGfm);
const squash = (s) => s.replace(/\s+/g, "");
// Markup or junk inside text nodes, beyond what the source text itself contains (e.g. "**" footnote marks)
const JUNK = /\*\*|&amp;|&nbsp;|<br/gi;
const failures = { text: [], html: [], literal: [], link: [], structure: [] };

for (const line of lines) {
  const { key, md, expected, structure } = JSON.parse(line);
  const tree = processor.runSync(processor.parse(md));
  const got = { heading: 0, blockquote: 0, table: 0 };
  let literal = 0;
  const walk = (n) => {
    if (n.type in got) got[n.type]++;
    if (n.type === "text") literal += (n.value.match(JUNK) || []).length;
    if (n.type === "html") failures.html.push({ key, value: n.value });
    if (n.type === "link" && !/^(https?:\/\/|mailto:)/i.test(n.url)) failures.link.push({ key, url: n.url });
    (n.children || []).forEach(walk);
  };
  walk(tree);

  const text = squash(toString(tree));
  const want = squash(expected);
  if (text !== want) {
    let i = 0;
    while (i < text.length && text[i] === want[i]) i++;
    failures.text.push({ key, got: text.slice(Math.max(0, i - 30), i + 40), want: want.slice(Math.max(0, i - 30), i + 40) });
  }
  if (literal > (expected.match(JUNK) || []).length) failures.literal.push({ key, literal });
  if (JSON.stringify(got) !== JSON.stringify(structure)) failures.structure.push({ key, got, want: structure });
}

console.log(`Checked ${lines.length} markdown values`);
for (const [kind, list] of Object.entries(failures)) {
  console.log(`  ${kind} failures: ${list.length}`);
  for (const f of list.slice(0, 5)) console.log("    ", JSON.stringify(f));
}
process.exit(Object.values(failures).some((list) => list.length) ? 1 : 0);
