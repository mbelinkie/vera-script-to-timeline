/** The source kinds currently exposed by Research's LibrarySource contract. */
export type MlaSourceKind =
  | "youtube"
  | "web_page"
  | "pdf"
  | "offline"
  | "image"
  | "audio"
  | "local_video"
  | "provider_video";

export type MlaField<T> = {
  value: T;
  state?: "automatic" | "confirmed";
};

export type MlaBibliography = {
  title?: MlaField<string>;
  authors?: MlaField<readonly string[]>;
  publication?: MlaField<string>;
  publisher?: MlaField<string>;
  date?: MlaField<string>;
  url?: MlaField<string>;
  credit?: MlaField<string>;
};

/**
 * Deliberately structural so this package does not depend on Research's
 * runtime package. The index signature keeps all of Research's per-kind
 * details assignable while the formatter reads only these shared properties.
 */
export type MlaSourceDetails = {
  channel?: string;
  accessedDate?: string;
  submittedUrl?: string;
  subtype?: string;
  [key: string]: unknown;
};

export type MlaSourceIdentity = {
  schemaVersion?: 1;
  provider?: string;
  providerMediaId?: string;
  canonicalUrl?: string;
};

/** The Research LibrarySource fields needed to create a citation. */
export type MlaSource = {
  kind: MlaSourceKind;
  bibliography: MlaBibliography;
  details: MlaSourceDetails;
  sourceIdentity?: MlaSourceIdentity;
};

type CitationSegment = {
  text: string;
  italicText?: string;
};

type CitationSpan = {
  start: number;
  end: number;
};

const MLA_MONTHS = new Map<string, string>([
  ["january", "Jan."],
  ["jan", "Jan."],
  ["jan.", "Jan."],
  ["february", "Feb."],
  ["feb", "Feb."],
  ["feb.", "Feb."],
  ["march", "Mar."],
  ["mar", "Mar."],
  ["mar.", "Mar."],
  ["april", "Apr."],
  ["apr", "Apr."],
  ["apr.", "Apr."],
  ["may", "May"],
  ["june", "June"],
  ["jun", "June"],
  ["jun.", "June"],
  ["july", "July"],
  ["jul", "July"],
  ["jul.", "July"],
  ["august", "Aug."],
  ["aug", "Aug."],
  ["aug.", "Aug."],
  ["september", "Sept."],
  ["sep", "Sept."],
  ["sep.", "Sept."],
  ["sept", "Sept."],
  ["sept.", "Sept."],
  ["october", "Oct."],
  ["oct", "Oct."],
  ["oct.", "Oct."],
  ["november", "Nov."],
  ["nov", "Nov."],
  ["nov.", "Nov."],
  ["december", "Dec."],
  ["dec", "Dec."],
  ["dec.", "Dec."],
]);

const MLA_MONTHS_BY_NUMBER = [
  "Jan.",
  "Feb.",
  "Mar.",
  "Apr.",
  "May",
  "June",
  "July",
  "Aug.",
  "Sept.",
  "Oct.",
  "Nov.",
  "Dec.",
];

const VIDEO_PLATFORMS = new Map<string, string>([
  ["facebook", "Facebook"],
  ["instagram", "Instagram"],
  ["tiktok", "TikTok"],
  ["youtube", "YouTube"],
]);

function normalizeWhitespace(value: string): string {
  return value.trim().replace(/\s+/gu, " ");
}

function textValue(field: MlaField<string> | undefined): string | undefined {
  if (typeof field?.value !== "string") return undefined;
  const value = normalizeWhitespace(field.value);
  return value || undefined;
}

function detailText(value: unknown): string | undefined {
  return typeof value === "string" ? textValue({ value }) : undefined;
}

function codePointLength(value: string): number {
  return Array.from(value).length;
}

function monthName(value: string): string | undefined {
  if (/^\d{1,2}$/u.test(value)) return MLA_MONTHS_BY_NUMBER[Number(value) - 1];
  return MLA_MONTHS.get(value.toLowerCase());
}

function validDay(value: string): boolean {
  const day = Number(value);
  return Number.isInteger(day) && day >= 1 && day <= 31;
}

function formatDate(value: string | undefined): string | undefined {
  const date = value ? normalizeWhitespace(value) : undefined;
  if (!date) return undefined;

  const iso = /^(\d{4})-(\d{2})(?:-(\d{2}))?(?:T.*)?$/u.exec(date);
  if (iso) {
    const [, year, month, day] = iso;
    const formattedMonth = monthName(String(Number(month)));
    if (!formattedMonth) return date;
    if (!day) return `${formattedMonth} ${year}`;
    if (!validDay(day)) return date;
    return `${Number(day)} ${formattedMonth} ${year}`;
  }

  const dayFirst = /^(\d{1,2})\s+([\p{L}.]+),?\s+(\d{4})$/u.exec(date);
  if (dayFirst) {
    const [, day, month, year] = dayFirst;
    if (!day || !month || !year) return date;
    const formattedMonth = monthName(month);
    if (formattedMonth && validDay(day)) return `${Number(day)} ${formattedMonth} ${year}`;
    return date;
  }

  const monthFirst = /^([\p{L}.]+)\s+(\d{1,2}),?\s+(\d{4})$/u.exec(date);
  if (monthFirst) {
    const [, month, day, year] = monthFirst;
    if (!month || !day || !year) return date;
    const formattedMonth = monthName(month);
    if (formattedMonth && validDay(day)) return `${Number(day)} ${formattedMonth} ${year}`;
    return date;
  }

  const monthAndYear = /^([\p{L}.]+)\s+(\d{4})$/u.exec(date);
  if (monthAndYear) {
    const [, month, year] = monthAndYear;
    if (!month || !year) return date;
    const formattedMonth = monthName(month);
    if (formattedMonth) return `${formattedMonth} ${year}`;
  }

  return date;
}

function sentencePeriod(value: string): string {
  return /[.!?]$/u.test(value) ? value : `${value}.`;
}

function quoteTitle(value: string): string {
  return `"${sentencePeriod(value)}"`;
}

function formatName(value: string, invert: boolean): string {
  const name = normalizeWhitespace(value);
  // A comma is the source's explicit inversion; otherwise only the final
  // token is a best-effort family name because free-form input cannot prove a
  // multipart surname.
  if (!invert || !name.includes(",")) {
    if (!invert) {
      const comma = name.indexOf(",");
      if (comma >= 0) {
        const family = name.slice(0, comma).trim();
        const given = name.slice(comma + 1).trim();
        return given ? `${given} ${family}` : family;
      }
    }
    if (!invert) return name;
  }

  if (name.includes(",")) return name.replace(/,\s*/gu, ", ");
  const words = name.split(" ");
  if (words.length < 2) return name;
  const family = words.pop();
  return family ? `${family}, ${words.join(" ")}` : name;
}

function formatAuthors(authors: readonly string[] | undefined): string | undefined {
  const values = authors
    ?.map((author) => (typeof author === "string" ? normalizeWhitespace(author) : ""))
    .filter((author) => author.length > 0);
  if (!values?.length) return undefined;

  const first = formatName(values[0]!, true);
  if (values.length === 1) return first;
  if (values.length === 2) return `${first}, and ${formatName(values[1]!, false)}`;
  return `${first}, et al.`;
}

function formatLocation(value: string | undefined): string | undefined {
  const location = value ? normalizeWhitespace(value) : undefined;
  if (!location) return undefined;
  if (/^(?:p\.?|pp\.?|page|pages)\s*/iu.test(location)) return location;
  if (/^\d+\s*[-–—]\s*\d+$/u.test(location)) return `pp. ${location}`;
  if (/^\d+$/u.test(location)) return `p. ${location}`;
  return location;
}

function platformFor(source: MlaSource, publication: string | undefined): string | undefined {
  if (source.kind === "youtube") return "YouTube";
  const provider = source.sourceIdentity?.provider?.trim().toLowerCase();
  return (provider ? VIDEO_PLATFORMS.get(provider) : undefined) ?? publication;
}

export function isCitationUrl(value: unknown): value is string {
  if (typeof value !== "string" || !/^https?:\/\//iu.test(value) || /[\p{Cc}\p{Surrogate}\s]/u.test(value)) return false;
  const url = URL.parse(value);
  return url !== null && url.username === "" && url.password === "";
}

function fullUrl(source: MlaSource): string | undefined {
  return [source.bibliography.url?.value, source.details.submittedUrl, source.sourceIdentity?.canonicalUrl]
    .find(isCitationUrl);
}

function makeCitation(segments: readonly CitationSegment[]): {
  citationText: string;
  italicSpan: CitationSpan | null;
} {
  const parts: string[] = [];
  let italicSpan: CitationSpan | null = null;
  let offset = 0;

  for (const segment of segments) {
    if (parts.length > 0) offset += 1;
    parts.push(segment.text);
    if (segment.italicText && italicSpan === null) {
      italicSpan = {
        // QuoteBoxV2 stores Unicode-safe zero-based, half-open ranges.
        start: offset,
        end: offset + codePointLength(segment.italicText),
      };
    }
    offset += codePointLength(segment.text);
  }

  return { citationText: parts.join(" "), italicSpan };
}

export function formatMlaCitation(
  source: MlaSource,
  options: { full?: boolean; location?: string } = {},
): { citationText: string; italicSpan: { start: number; end: number } | null } {
  const title = textValue(source.bibliography.title);
  const publication = textValue(source.bibliography.publication);
  const publisher = textValue(source.bibliography.publisher);
  const date = formatDate(textValue(source.bibliography.date));
  const authors = formatAuthors(source.bibliography.authors?.value);
  const details = source.details;
  const isVideo =
    source.kind === "youtube" ||
    source.kind === "provider_video" ||
    source.kind === "local_video";
  const isBook = source.kind === "offline" && details.subtype === "book";
  const container = isBook ? title : isVideo ? platformFor(source, publication) : publication;
  const location = formatLocation(options.location);
  const accessedDate = options.full ? formatDate(detailText(details.accessedDate)) : undefined;
  const tail: string[] = [];

  if (isVideo) {
    const channel = detailText(details.channel);
    if (channel) tail.push(`uploaded by ${channel}`);
  }
  if (publisher) tail.push(publisher);
  if (date) tail.push(date);
  if (location) tail.push(location);
  if (options.full) {
    const url = fullUrl(source);
    if (url) tail.push(url);
  }

  const segments: CitationSegment[] = [];
  if (authors) segments.push({ text: sentencePeriod(authors) });

  if (isBook) {
    if (title) segments.push({ text: sentencePeriod(title), italicText: title });
    if (tail.length) segments.push({ text: sentencePeriod(tail.join(", ")) });
  } else {
    if (title) segments.push({ text: quoteTitle(title) });
    if (container) {
      segments.push({
        text: sentencePeriod([container, ...tail].join(", ")),
        italicText: container,
      });
    } else if (tail.length) {
      segments.push({ text: sentencePeriod(tail.join(", ")) });
    }
  }

  if (accessedDate) segments.push({ text: sentencePeriod(`Accessed ${accessedDate}`) });

  return makeCitation(segments);
}
