export type CitablePaper = {
  title: string;
  authors: string[];
  journal: string | null;
  year: number | null;
  doi: string | null;
  url: string | null;
  paper_type: string | null;
};

type ParsedName = { family: string; given: string };

// Names in the corpus are stored display-style ("M G F Hossain"), so the
// last token is treated as the family name and the rest as given names.
function parseName(name: string): ParsedName {
  const tokens = name.trim().split(/\s+/);
  if (tokens.length <= 1) return { family: name.trim(), given: "" };
  return { family: tokens[tokens.length - 1], given: tokens.slice(0, -1).join(" ") };
}

function givenInitials(given: string): string {
  return given
    .split(/[\s.]+/)
    .filter(Boolean)
    .map((part) => `${part[0].toUpperCase()}.`)
    .join(" ");
}

function bibtexEscape(text: string): string {
  return text.replace(/([&%#_$])/g, "\\$1");
}

function bibtexType(paperType: string | null): string {
  switch (paperType) {
    case "Book Chapter":
      return "incollection";
    case "Thesis":
      return "phdthesis";
    case "Journal Article":
    case "Review":
      return "article";
    default:
      return "misc";
  }
}

function risType(paperType: string | null): string {
  switch (paperType) {
    case "Book Chapter":
      return "CHAP";
    case "Thesis":
      return "THES";
    case "Journal Article":
    case "Review":
      return "JOUR";
    default:
      return "GEN";
  }
}

export function citationKey(paper: CitablePaper): string {
  const firstAuthor = paper.authors[0] ? parseName(paper.authors[0]).family : "anon";
  const firstWord = (paper.title.match(/[A-Za-z]{3,}/) || ["paper"])[0];
  return `${firstAuthor}${paper.year ?? ""}${firstWord}`
    .toLowerCase()
    .replace(/[^a-z0-9]/g, "");
}

export function toBibtex(paper: CitablePaper): string {
  const type = bibtexType(paper.paper_type);
  const authorField = paper.authors
    .map((name) => {
      const { family, given } = parseName(name);
      return given ? `${family}, ${given}` : family;
    })
    .join(" and ");

  const lines: string[] = [];
  lines.push(`@${type}{${citationKey(paper)},`);
  lines.push(`  title = {${bibtexEscape(paper.title)}},`);
  if (authorField) lines.push(`  author = {${bibtexEscape(authorField)}},`);
  if (paper.journal) {
    const field = type === "incollection" ? "booktitle" : type === "article" ? "journal" : "howpublished";
    lines.push(`  ${field} = {${bibtexEscape(paper.journal)}},`);
  }
  if (paper.year) lines.push(`  year = {${paper.year}},`);
  if (paper.doi) lines.push(`  doi = {${paper.doi}},`);
  if (paper.doi || paper.url) lines.push(`  url = {${paper.url || `https://doi.org/${paper.doi}`}},`);
  // Strip the trailing comma on the last field line.
  lines[lines.length - 1] = lines[lines.length - 1].replace(/,$/, "");
  lines.push("}");
  return lines.join("\n");
}

export function toRis(paper: CitablePaper): string {
  const lines: string[] = [`TY  - ${risType(paper.paper_type)}`];
  for (const name of paper.authors) {
    const { family, given } = parseName(name);
    lines.push(`AU  - ${given ? `${family}, ${given}` : family}`);
  }
  lines.push(`TI  - ${paper.title}`);
  if (paper.journal) lines.push(`T2  - ${paper.journal}`);
  if (paper.year) lines.push(`PY  - ${paper.year}`);
  if (paper.doi) lines.push(`DO  - ${paper.doi}`);
  if (paper.url || paper.doi) lines.push(`UR  - ${paper.url || `https://doi.org/${paper.doi}`}`);
  lines.push("ER  - ");
  return lines.join("\n");
}

export function toApa(paper: CitablePaper): string {
  const formatted = paper.authors.map((name) => {
    const { family, given } = parseName(name);
    return given ? `${family}, ${givenInitials(given)}` : family;
  });

  let authorPart = "";
  if (formatted.length === 1) {
    authorPart = formatted[0];
  } else if (formatted.length <= 20) {
    authorPart = `${formatted.slice(0, -1).join(", ")}, & ${formatted[formatted.length - 1]}`;
  } else {
    // APA 7: first 19 authors, ellipsis, then the final author.
    authorPart = `${formatted.slice(0, 19).join(", ")}, ... ${formatted[formatted.length - 1]}`;
  }

  const yearPart = `(${paper.year ?? "n.d."})`;
  const title = paper.title.replace(/\.$/, "");
  const journalPart = paper.journal ? ` ${paper.journal}.` : "";
  const link = paper.doi ? ` https://doi.org/${paper.doi}` : paper.url ? ` ${paper.url}` : "";

  return `${authorPart ? `${authorPart} ` : ""}${yearPart}. ${title}.${journalPart}${link}`.trim();
}
