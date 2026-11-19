import type { Page } from "playwright";

import { CaptureDenied } from "./policy.js";

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

type PassageEvaluation =
  | { readonly kind: "rects"; readonly rects: PassageRect[] }
  | { readonly kind: "failure"; readonly reason: string };

/** Locate one visible rendered passage and return its 2x viewport rectangles. */
export async function locatePassage(
  page: Page,
  request: PassageRequest,
): Promise<PassageRect[]> {
  const result: PassageEvaluation = await page.evaluate(async ({ exact, prefix, suffix }) => {
    const knownFailureMessages = new Set([
      "Passage exact text is empty.",
      "Rendered text exceeds locator budget.",
      "Passage was ambiguous.",
      "Passage was not found.",
      "Passage was not visible.",
      "Passage was clipped.",
      "Passage geometry exceeded the maximum of 64 rectangles.",
    ]);
    try {
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
        ancestorElements(node: Text): Element[] {
          const result: Element[] = [];
          let element = node.parentElement;
          while (element) {
            result.push(element);
            element = element.parentElement;
          }
          return result;
        },
        elementDepth(element: Element): number {
          let depth = 0;
          while (element.parentElement) {
            depth += 1;
            element = element.parentElement;
          }
          return depth;
        },
        isClippedByAncestor(rect: DOMRect, parents: readonly Element[]): boolean {
          for (const ancestor of parents) {
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
        locateFragments(start: number, end: number): PassageFragment[] {
          const fragments: PassageFragment[] = [];
          for (const segment of segments) {
            if (segment.end <= start) continue;
            if (segment.start >= end) break;
            const rawStart = segment.rawStart + (segment.collapsed ? 0 : Math.max(0, start - segment.start));
            const rawEnd = segment.rawEnd - (segment.collapsed ? 0 : Math.max(0, segment.end - end));
            if (rawEnd <= rawStart) continue;
            const previous = fragments.at(-1);
            if (previous?.range.startContainer === segment.node && previous.range.endOffset === rawStart) {
              previous.range.setEnd(segment.node, rawEnd);
              continue;
            }
            const range = document.createRange();
            range.setStart(segment.node, rawStart);
            range.setEnd(segment.node, rawEnd);
            fragments.push({ range, parents: dom.ancestorElements(segment.node) });
          }
          return fragments;
        },
        scrollNestedContainers(fragments: readonly PassageFragment[]): void {
          const byContainer = new Map<HTMLElement, Range[]>();
          for (const { range, parents } of fragments) {
            for (const parent of parents) {
              if (!(parent instanceof HTMLElement) || parent === document.scrollingElement) continue;
              const ranges = byContainer.get(parent);
              if (ranges) ranges.push(range);
              else byContainer.set(parent, [range]);
            }
          }
          const containers = [...byContainer].sort(([left], [right]) =>
            dom.elementDepth(right) - dom.elementDepth(left),
          );
          for (const [container, ranges] of containers) {
            const style = getComputedStyle(container);
            const scrollsX = (style.overflowX === "auto" || style.overflowX === "scroll") &&
              container.scrollWidth > container.clientWidth;
            const scrollsY = (style.overflowY === "auto" || style.overflowY === "scroll") &&
              container.scrollHeight > container.clientHeight;
            if (!scrollsX && !scrollsY) continue;
            const target = dom.bounds(ranges.map((range) => range.getBoundingClientRect()));
            if (!target) continue;
            const box = container.getBoundingClientRect();
            container.scrollBy({
              left: scrollsX ? target.left + target.width / 2 - (box.left + box.width / 2) : 0,
              top: scrollsY ? target.top + target.height / 2 - (box.top + box.height / 2) : 0,
              behavior: "instant",
            });
          }
        },
        bounds(rects: readonly DOMRect[]): DOMRect | null {
          const visible = rects.filter((rect) => rect.width > 0 && rect.height > 0);
          if (visible.length === 0) return null;
          const left = Math.min(...visible.map((rect) => rect.left));
          const top = Math.min(...visible.map((rect) => rect.top));
          const right = Math.max(...visible.map((rect) => rect.right));
          const bottom = Math.max(...visible.map((rect) => rect.bottom));
          return new DOMRect(left, top, right - left, bottom - top);
        },
        coalesce(rects: readonly DOMRect[]): DOMRect[] {
          const ordered = [...rects].sort((left, right) => left.left - right.left);
          const merged: DOMRect[] = [];
          for (const rect of ordered) {
            const adjacentLine = merged.findIndex((line) => {
              const centerDelta = Math.abs(
                (line.top + line.bottom) / 2 - (rect.top + rect.bottom) / 2,
              );
              return centerDelta <= Math.max(2, Math.min(line.height, rect.height) / 2) &&
                rect.left <= line.right + 1;
            });
            const line = merged[adjacentLine];
            if (!line) {
              if (merged.length === 64) {
                throw new Error("Passage geometry exceeded the maximum of 64 rectangles.");
              }
              merged.push(rect);
              continue;
            }
            const top = Math.min(line.top, rect.top);
            const right = Math.max(line.right, rect.right);
            const bottom = Math.max(line.bottom, rect.bottom);
            merged[adjacentLine] = new DOMRect(line.left, top, right - line.left, bottom - top);
          }
          return merged.sort((left, right) => left.top - right.top || left.left - right.left);
        },
      };
      const wanted = dom.normalize(exact);
      const before = prefix === undefined ? "" : dom.normalize(prefix);
      const after = suffix === undefined ? "" : dom.normalize(suffix);
      if (!wanted) throw new Error("Passage exact text is empty.");

      type PassageFragment = {
        readonly range: Range;
        readonly parents: readonly Element[];
      };
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

      const fragments = dom.locateFragments(matchStart, matchStart + wanted.length);
      dom.scrollNestedContainers(fragments);

      const initialBounds = dom.bounds(fragments.map(({ range }) => range.getBoundingClientRect()));
      if (!initialBounds) throw new Error("Passage was not visible.");
      window.scrollTo({
        left: window.scrollX + initialBounds.left + initialBounds.width / 2 - innerWidth / 2,
        top: window.scrollY + initialBounds.top + initialBounds.height / 2 - innerHeight / 2,
        behavior: "instant",
      });
      await new Promise<void>(function (resolve) {
        requestAnimationFrame(function () {
          requestAnimationFrame(function () { resolve(); });
        });
      });

      const rects: DOMRect[] = [];
      for (const { range, parents } of fragments) {
        for (const rect of range.getClientRects()) {
          if (rect.width <= 0 || rect.height <= 0) continue;
          if (dom.isClippedByAncestor(rect, parents)) throw new Error("Passage was clipped.");
          rects.push(rect);
        }
      }
      if (rects.length === 0) throw new Error("Passage was not visible.");
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

      const lineRects = dom.coalesce(rects);
      const scale = 2;
      return {
        kind: "rects" as const,
        rects: lineRects.map(function (rect) {
          const left = Math.max(0, Math.min(innerWidth, rect.left));
          const top = Math.max(0, Math.min(innerHeight, rect.top));
          const right = Math.max(0, Math.min(innerWidth, rect.right));
          const bottom = Math.max(0, Math.min(innerHeight, rect.bottom));
          const x = Math.floor(left * scale);
          const y = Math.floor(top * scale);
          const rightPixels = Math.ceil(right * scale);
          const bottomPixels = Math.ceil(bottom * scale);
          return {
            x,
            y,
            width: Math.max(0, rightPixels - x),
            height: Math.max(0, bottomPixels - y),
          };
        }),
      };
    } catch (error) {
      if (error instanceof Error && knownFailureMessages.has(error.message)) {
        return { kind: "failure" as const, reason: error.message };
      }
      throw error;
    }
  }, {
    exact: request.exact,
    ...(request.prefix === undefined ? {} : { prefix: request.prefix }),
    ...(request.suffix === undefined ? {} : { suffix: request.suffix }),
  });
  if (result.kind === "failure") {
    throw new CaptureDenied(
      "passage_unavailable",
      result.reason,
      "response",
      true,
    );
  }
  return result.rects;
}
