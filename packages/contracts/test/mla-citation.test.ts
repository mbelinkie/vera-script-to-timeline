import { describe, expect, it } from "vitest";

import { formatMlaCitation, type MlaSource } from "../src/mla-citation.js";

function source(overrides: Partial<MlaSource> = {}): MlaSource {
  return {
    kind: "web_page",
    bibliography: {
      title: { value: "A Note on Élan" },
      authors: { value: ["Ada Lovelace"] },
      publication: { value: "Journal of Examples" },
      date: { value: "2023-03-14" },
      url: { value: "https://example.com/article" },
    },
    details: { accessedDate: "2023-03-20" },
    ...overrides,
  };
}

describe("formatMlaCitation", () => {
  it("formats an article for the screen and computes one container span", () => {
    const result = formatMlaCitation(source());

    expect(result.citationText).toBe(
      'Lovelace, Ada. "A Note on Élan." Journal of Examples, 14 Mar. 2023.',
    );
    expect(result.citationText).not.toContain("https://");
    expect(result.citationText).not.toContain("Accessed");

    const start = Array.from('Lovelace, Ada. "A Note on Élan." ').length;
    expect(result.italicSpan).toEqual({
      start,
      end: start + Array.from("Journal of Examples").length,
    });
  });

  it("includes the URL and access date only in the full form", () => {
    const result = formatMlaCitation(source(), { full: true });

    expect(result.citationText).toBe(
      'Lovelace, Ada. "A Note on Élan." Journal of Examples, 14 Mar. 2023, https://example.com/article. Accessed 20 Mar. 2023.',
    );
    expect(result.italicSpan).toEqual({
      start: Array.from('Lovelace, Ada. "A Note on Élan." ').length,
      end: Array.from('Lovelace, Ada. "A Note on Élan." Journal of Examples').length,
    });
  });

  it("omits unsafe URL fields from full citations", () => {
    expect(formatMlaCitation(source({
      bibliography: { title: { value: "Title" }, url: { value: "https://example.test/article\nEXTRA" } },
      details: {},
    }), { full: true }).citationText).toBe('"Title."');
  });

  it("formats a book title as the container and includes its page", () => {
    const result = formatMlaCitation(
      source({
        kind: "offline",
        bibliography: {
          title: { value: "Cien años de soledad" },
          authors: { value: ["García Márquez, Gabriel"] },
          publisher: { value: "Harper" },
          date: { value: "1967" },
        },
        details: { subtype: "book" },
      }),
      { location: "42" },
    );

    expect(result.citationText).toBe(
      "García Márquez, Gabriel. Cien años de soledad. Harper, 1967, p. 42.",
    );
    const start = Array.from("Márquez, Gabriel García. ").length;
    expect(result.italicSpan).toEqual({
      start,
      end: start + Array.from("Cien años de soledad").length,
    });
  });

  it("drops absent author and date without inventing values", () => {
    const result = formatMlaCitation(
      source({
        bibliography: {
          title: { value: "An Uncredited Page" },
          publication: { value: "Example Site" },
        },
        details: {},
      }),
    );

    expect(result.citationText).toBe('"An Uncredited Page." Example Site.');
    expect(result.italicSpan).toEqual({
      start: Array.from('"An Uncredited Page." ').length,
      end: Array.from('"An Uncredited Page." Example Site').length,
    });
  });

  it("handles multiple accented authors without losing accents", () => {
    const result = formatMlaCitation(
      source({
        bibliography: {
          title: { value: "A Shared Discovery" },
          authors: { value: ["Zoë García", "Renée Dvořák"] },
          publication: { value: "The Review" },
        },
        details: {},
      }),
    );

    expect(result.citationText).toBe(
      'García, Zoë, and Renée Dvořák. "A Shared Discovery." The Review.',
    );
  });

  it("formats a print article with a quoted title and publication container", () => {
    const result = formatMlaCitation(
      source({
        kind: "offline",
        bibliography: {
          title: { value: "Notes from the Archive" },
          authors: { value: ["Susan Sontag"] },
          publication: { value: "The Printed Review" },
          date: { value: "14 March 2023" },
        },
        details: { subtype: "print_article" },
      }),
    );

    expect(result.citationText).toBe(
      'Sontag, Susan. "Notes from the Archive." The Printed Review, 14 Mar. 2023.',
    );
  });

  it("uses pp. for page ranges and leaves non-pagination locations untouched", () => {
    const book = source({
      kind: "offline",
      bibliography: {
        title: { value: "A Book" },
        publisher: { value: "A Press" },
      },
      details: { subtype: "book" },
    });
    const video = source({
      kind: "youtube",
      bibliography: { title: { value: "A Video" } },
      details: {},
    });

    expect(formatMlaCitation(book, { location: "42–43" }).citationText).toBe(
      "A Book. A Press, pp. 42–43.",
    );
    expect(formatMlaCitation(video, { location: "2:01" }).citationText).toBe(
      '"A Video." YouTube, 2:01.',
    );
  });

  it("formats a YouTube uploader and platform", () => {
    const result = formatMlaCitation(
      source({
        kind: "youtube",
        bibliography: {
          title: { value: "A Video Essay" },
          publication: { value: "Creator Site" },
          date: { value: "July 4, 2024" },
          url: { value: "https://youtu.be/example" },
        },
        details: { channel: "Béla Channel" },
      }),
    );

    expect(result.citationText).toBe(
      '"A Video Essay." YouTube, uploaded by Béla Channel, 4 July 2024.',
    );
    const start = Array.from('"A Video Essay." ').length;
    expect(result.italicSpan).toEqual({
      start,
      end: start + Array.from("YouTube").length,
    });
  });

  it("counts Unicode code points in the persisted half-open span", () => {
    const result = formatMlaCitation(
      source({
        bibliography: {
          title: { value: "🎬 A Story" },
          publication: { value: "Café Nord" },
        },
        details: {},
      }),
    );

    const prefix = '"🎬 A Story." ';
    expect(result.italicSpan).toEqual({
      start: Array.from(prefix).length,
      end: Array.from(prefix).length + Array.from("Café Nord").length,
    });
  });
});
