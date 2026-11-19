import type { Page } from "playwright";

export interface PassageRequest {
  readonly exact: string;
  readonly prefix?: string;
  readonly suffix?: string;
}

export interface PassageRect {
  readonly x: number;
  readonly y: number;
  readonly width: number;
  readonly height: number;
}

/** Locate one visible rendered passage and return its 2x viewport rectangles. */
export async function locatePassage(
  page: Page,
  request: PassageRequest,
): Promise<PassageRect[]> {
  return await page.evaluate(async ({ exact, prefix, suffix }) => {
    const MAX_TEXT_NODES = 50_000;
    const MAX_TEXT_CHARS = 1_000_000;
    const MAX_SEGMENTS = 250_000;
    // Playwright serializes this callback. Method syntax keeps tsx from
    // inserting references to its outer function-name helper into the page.
    const dom = {
      normalize(value: string): string {
        return value.replace(/\s+/gu, " ").trim();
      },
      isVisible(node: Text): boolean {
        let element = node.parentElement;
        while (element) {
          const cached = visibleCache.get(element);
          if (cached !== undefined) {
            if (!cached) return false;
            element = element.parentElement;
            continue;
          }
          const style = getComputedStyle(element);
          const elementVisible = !(
            style.display === "none" ||
            style.visibility === "hidden" ||
            style.visibility === "collapse" ||
            style.contentVisibility === "hidden" ||
            Number(style.opacity) === 0
          );
          visibleCache.set(element, elementVisible);
          if (!elementVisible) return false;
          element = element.parentElement;
        }
        return true;
      },
      nearestBlock(node: Text): Element | null {
        let element = node.parentElement;
        while (element) {
          if (blockDisplay.has(getComputedStyle(element).display)) return element;
          element = element.parentElement;
        }
        return null;
      },
      append(
        value: string,
        node: Text,
        rawStart: number,
        rawEnd: number,
        collapsed = false,
      ): void {
        if (!value) return;
        if (segments.length >= MAX_SEGMENTS) {
          throw new Error("Rendered text exceeds locator budget.");
        }
        chunks.push(value);
        segments.push({
          start: streamLength,
          end: streamLength + value.length,
          node,
          rawStart,
          rawEnd,
          collapsed,
        });
        streamLength += value.length;
        lastOutputWasSpace = value.endsWith(" ");
      },
      flushSpace(): void {
        if (!pendingSpace) return;
        dom.append(
          " ",
          pendingSpace.node,
          pendingSpace.start,
          pendingSpace.end,
          true,
        );
        pendingSpace = null;
      },
      appendBoundary(node: Text): void {
        dom.flushSpace();
        if (streamLength > 0 && !lastOutputWasSpace) {
          const offset = node.nodeValue?.length ?? 0;
          dom.append(" ", node, offset, offset, true);
        }
      },
      appendText(node: Text): void {
        const value = node.nodeValue ?? "";
        for (let offset = 0; offset < value.length; ) {
          const character = value[offset];
          if (character === undefined) break;
          if (/\s/u.test(character)) {
            const start = offset;
            while (offset < value.length && /\s/u.test(value[offset] ?? "")) {
              offset += 1;
            }
            if (streamLength > 0 || chunks.length > 0) {
              pendingSpace = {
                node,
                start,
                end: offset,
              };
            }
            continue;
          }
          dom.flushSpace();
          const start = offset;
          while (
            offset < value.length &&
            !/\s/u.test(value[offset] ?? "")
          ) {
            offset += 1;
          }
          dom.append(value.slice(start, offset), node, start, offset);
        }
      },
      positionAt(index: number, bias: "start" | "end"): Position {
        if (bias === "end") {
          const segment = segments.find(function (candidate) {
            return candidate.start <= index - 1 && index - 1 < candidate.end;
          });
          if (!segment) throw new Error("Passage was not found.");
          if (segment.collapsed) {
            return { node: segment.node, offset: segment.rawEnd };
          }
          return {
            node: segment.node,
            offset: segment.rawStart + (index - segment.start),
          };
        }
        const segment = segments.find(function (candidate) {
          return candidate.start <= index && index < candidate.end;
        });
        if (!segment) throw new Error("Passage was not found.");
        return {
          node: segment.node,
          offset: segment.rawStart + (index - segment.start),
        };
      },
      prefixMatches(start: number): boolean {
        if (!before) return true;
        let end = start;
        while (end > 0 && /\s/u.test(rendered[end - 1] ?? "")) end -= 1;
        const contextStart = end - before.length;
        return contextStart >= 0 && rendered.startsWith(before, contextStart);
      },
      suffixMatches(end: number): boolean {
        if (!after) return true;
        let start = end;
        while (start < rendered.length && /\s/u.test(rendered[start] ?? "")) {
          start += 1;
        }
        return rendered.startsWith(after, start);
      },
      ancestorElements(position: Position): Element[] {
        const result: Element[] = [];
        let element = position.node.parentElement;
        while (element) {
          result.push(element);
          element = element.parentElement;
        }
        return result;
      },
      isClippedByAncestor(rect: DOMRect): boolean {
        for (const ancestor of ancestors) {
          const style = getComputedStyle(ancestor);
          const clipsX = style.overflowX !== "visible";
          const clipsY = style.overflowY !== "visible";
          if (!clipsX && !clipsY) continue;
          const box = ancestor.getBoundingClientRect();
          if (
            (clipsX && (rect.left < box.left || rect.right > box.right)) ||
            (clipsY && (rect.top < box.top || rect.bottom > box.bottom))
          ) {
            return true;
          }
        }
        return false;
      },
      visibleRects(): DOMRect[] {
        return Array.from(range.getClientRects()).filter(function (rect) {
          return rect.width > 0 && rect.height > 0;
        });
      },
    };
    const wanted = dom.normalize(exact);
    const before = prefix === undefined ? "" : dom.normalize(prefix);
    const after = suffix === undefined ? "" : dom.normalize(suffix);
    if (!wanted) throw new Error("Passage exact text is empty.");

    type Position = { readonly node: Text; readonly offset: number };
    type Segment = {
      readonly start: number;
      readonly end: number;
      readonly node: Text;
      readonly rawStart: number;
      readonly rawEnd: number;
      readonly collapsed: boolean;
    };
    type PendingSpace = {
      readonly node: Text;
      readonly start: number;
      readonly end: number;
    };

    const visibleCache = new WeakMap<Element, boolean>();

    const root = document.body ?? document.documentElement;
    const countWalker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    let textNodeCount = 0;
    let rawCharacterCount = 0;
    let counted = countWalker.nextNode();
    while (counted) {
      textNodeCount += 1;
      rawCharacterCount += counted.nodeValue?.length ?? 0;
      if (
        textNodeCount > MAX_TEXT_NODES ||
        rawCharacterCount > MAX_TEXT_CHARS
      ) {
        throw new Error("Rendered text exceeds locator budget.");
      }
      counted = countWalker.nextNode();
    }

    const blockDisplay = new Set([
      "block",
      "flow-root",
      "flex",
      "grid",
      "table",
      "table-caption",
      "table-cell",
      "table-row",
      "list-item",
    ]);

    const chunks: string[] = [];
    const segments: Segment[] = [];
    let streamLength = 0;
    let pendingSpace: PendingSpace | null = null;
    let previousText: Text | null = null;
    let previousBlock: Element | null = null;
    let lastOutputWasSpace = false;


    const walker = document.createTreeWalker(
      root,
      NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT,
    );
    let current = walker.nextNode();
    while (current) {
      if (current.nodeType === Node.TEXT_NODE) {
        const text = current as Text;
        if (dom.isVisible(text)) {
          const block = dom.nearestBlock(text);
          if (previousText && block !== previousBlock) dom.appendBoundary(previousText);
          dom.appendText(text);
          previousText = text;
          previousBlock = block;
        }
      } else if (
        current.nodeType === Node.ELEMENT_NODE &&
        (current as Element).tagName === "BR"
      ) {
        if (previousText && dom.isVisible(previousText)) dom.appendBoundary(previousText);
      }
      current = walker.nextNode();
    }
    const rendered = chunks.join("");



    let matchStart: number | null = null;
    let searchFrom = 0;
    while (true) {
      const start = rendered.indexOf(wanted, searchFrom);
      if (start < 0) break;
      const end = start + wanted.length;
      if (dom.prefixMatches(start) && dom.suffixMatches(end)) {
        if (matchStart !== null) throw new Error("Passage was ambiguous.");
        matchStart = start;
      }
      searchFrom = start + 1;
    }
    if (matchStart === null) throw new Error("Passage was not found.");

    const startPosition = dom.positionAt(matchStart, "start");
    const endPosition = dom.positionAt(matchStart + wanted.length, "end");
    const range = document.createRange();
    range.setStart(startPosition.node, startPosition.offset);
    range.setEnd(endPosition.node, endPosition.offset);

    const ancestors = [
      ...new Set([
        ...dom.ancestorElements(startPosition),
        ...dom.ancestorElements(endPosition),
      ]),
    ];
    const initialRects = dom.visibleRects();
    if (initialRects.length === 0) throw new Error("Passage was not visible.");
    if (initialRects.some((rect) => dom.isClippedByAncestor(rect))) throw new Error("Passage was clipped.");

    const initialBounds = range.getBoundingClientRect();
    window.scrollTo(
      window.scrollX + initialBounds.left + initialBounds.width / 2 - innerWidth / 2,
      window.scrollY + initialBounds.top + initialBounds.height / 2 - innerHeight / 2,
    );
    await new Promise<void>(function (resolve) {
      requestAnimationFrame(function () {
        requestAnimationFrame(function () { resolve(); });
      });
    });

    const rects = dom.visibleRects();
    if (rects.length === 0) throw new Error("Passage was not visible.");
    if (rects.some((rect) => dom.isClippedByAncestor(rect))) throw new Error("Passage was clipped.");
    if (
      rects.some(function (rect) {
        return (
          rect.left < 0 ||
          rect.top < 0 ||
          rect.right > innerWidth ||
          rect.bottom > innerHeight
        );
      })
    ) {
      throw new Error("Passage was clipped.");
    }

    return rects
      .sort(function (left, right) {
        return left.top - right.top || left.left - right.left;
      })
      .map(function (rect) {
        return {
          x: Math.round(rect.left * 2),
          y: Math.round(rect.top * 2),
          width: Math.round(rect.width * 2),
          height: Math.round(rect.height * 2),
        };
      });
  }, {
    exact: request.exact,
    ...(request.prefix === undefined ? {} : { prefix: request.prefix }),
    ...(request.suffix === undefined ? {} : { suffix: request.suffix }),
  });
}
