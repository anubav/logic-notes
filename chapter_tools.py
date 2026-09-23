"""
Shared utilities for coarse-graining and cleaning up the logic-notes chapters.

Two independent passes, kept separate on purpose:
  1. merge_chapter(): concatenate a wrapper chapter's included section files,
     in the wrapper's original include order, stripping any existing
     content-hidden/when-profile wrapping and adding {#sec-...} labels to any
     ## heading that lacks one. Chapter-level # heading gets its own label +
     .chapter class if missing.
  2. reflow(): cosmetic cleanup only -- standardize blank-line spacing and
     wrap long prose paragraphs to a target column width, without touching
     fenced code/div blocks, display math, tables, lists, or headings.

Both passes are fence-aware: they track ``` code fences and ::: div fences
so that headings/text INSIDE a fenced environment (e.g. an lproof
.theorem/.definition/.example div, which may itself contain a heading-styled
title line) are never mistaken for top-level document structure.
"""

import re
from pathlib import Path

CODE_FENCE_RE = re.compile(r'^\s*```')
MATH_FENCE_RE = re.compile(r'^\s*\$\$\s*$')
DIV_FENCE_RE = re.compile(r'^(\s*)(:{3,})(.*)$')
THEMATIC_BREAK_RE = re.compile(r'^\s*([-*_])(?:\s*\1){2,}\s*$')
HEADING_RE = re.compile(r'^(#{1,6})\s+(.*)$')
LABEL_RE = re.compile(r'\{#([\w-]+)[^}]*\}')
ATTR_BLOCK_RE = re.compile(r'\{([^}]*)\}\s*$')
INCLUDE_RE = re.compile(r'\{\{<\s*include\s+([^\s>]+)\s*>\}\}')


class FenceTracker:
    """Tracks code-fence, display-math-fence, and div-fence depth line by
    line. Two distinct notions of 'top level' are exposed:
      - at_structural_top_level(): used when deciding whether a '#'/'##'
        line is real document structure (must be outside code, math, AND
        any div -- a heading inside a .theorem div is a decorative title,
        not a section).
      - in_protected_block(): used when deciding whether prose text may be
        reflowed. Code and display-math blocks are hard-protected. So is
        any .lproof div, in full, regardless of what its individual lines
        look like -- lproof's own parser reads its content as raw text
        (each line indented >=4 spaces, carrying its own line number), so
        reflow must never rejoin, rewrap, or trim anything inside one.
        Protection is inherited by anything nested inside an .lproof div.
    """

    LPROOF_OPEN_RE = re.compile(r'^(\s*)(:{3,})\{[^}]*\.lproof[^}]*\}\s*$')

    def __init__(self):
        self.in_code = False
        self.in_math = False
        self.div_depth = 0
        self.lproof_stack = []  # one bool per open div: is it (or its parent) lproof?

    def at_structural_top_level(self):
        return (not self.in_code) and (not self.in_math) and self.div_depth == 0

    def in_protected_block(self):
        if self.in_code or self.in_math:
            return True
        return bool(self.lproof_stack) and self.lproof_stack[-1]

    def consume(self, line):
        """Update state for this line, return True if this line itself
        is a fence delimiter (code, math, or div) rather than content."""
        if CODE_FENCE_RE.match(line):
            self.in_code = not self.in_code
            return True
        if self.in_code:
            return False
        if MATH_FENCE_RE.match(line):
            self.in_math = not self.in_math
            return True
        if self.in_math:
            return False
        m = DIV_FENCE_RE.match(line)
        if m:
            colons = m.group(2)
            rest = m.group(3).strip()
            if rest:  # opening fence, e.g. ':::{.content-hidden ...}'
                self.div_depth += 1
                is_lproof = bool(re.search(r'\.lproof\b', rest))
                inherited = bool(self.lproof_stack) and self.lproof_stack[-1]
                self.lproof_stack.append(is_lproof or inherited)
            else:     # bare ':::' -- closes the innermost open div
                if self.div_depth > 0:
                    self.div_depth -= 1
                if self.lproof_stack:
                    self.lproof_stack.pop()
            return True
        return False


def slugify(text: str) -> str:
    # strip inline math, footnote/citation markers, existing {#...} attrs
    text = re.sub(r'\$[^$]*\$', '', text)
    text = LABEL_RE.sub('', text)
    text = re.sub(r'\[\^[^\]]*\]', '', text)
    text = re.sub(r'\\[A-Za-z]+', '', text)
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', '-', text)
    return text.strip('-')


def add_missing_labels(text: str, chapter_slug: str) -> str:
    """Add {#sec-<chapter>-<heading>} to any top-level (fence-depth 0)
    '##' heading lacking a label. Leaves '#' (chapter title) and any
    heading at fence-depth > 0 untouched; caller handles the chapter
    title label separately."""
    lines = text.split('\n')
    out = []
    tracker = FenceTracker()
    for line in lines:
        is_fence = tracker.consume(line)
        if not is_fence and tracker.at_structural_top_level():
            m = HEADING_RE.match(line)
            if m and len(m.group(1)) == 2:  # '##' only
                if not LABEL_RE.search(line):
                    slug = f'sec-{chapter_slug}-{slugify(m.group(2))}'
                    attr_m = ATTR_BLOCK_RE.search(line.rstrip())
                    if attr_m:
                        # existing {.class ...} block with no #id -- merge in
                        inner = attr_m.group(1).strip()
                        new_attr = '{#' + slug + (' ' + inner if inner else '') + '}'
                        line = line.rstrip()[:attr_m.start()] + new_attr
                    else:
                        line = line.rstrip() + f' {{#{slug}}}'
        out.append(line)
    return '\n'.join(out)


def strip_profile_wrapping(text: str) -> str:
    """Remove any :::{.content-hidden when-profile=...} wrapper divs
    (and their matching closing :::), keeping their inner content.
    Old per-year hand-authored hiding logic has no place in the pristine
    master -- instrumentation is generated fresh at build time instead."""
    lines = text.split('\n')
    out = []
    skip_stack = []  # True = this open fence was a content-hidden wrapper we're dropping
    for line in lines:
        m = DIV_FENCE_RE.match(line)
        if m:
            rest = m.group(3).strip()
            if rest:
                is_hidden_wrapper = 'content-hidden' in rest and 'when-profile' in rest
                skip_stack.append(is_hidden_wrapper)
                if is_hidden_wrapper:
                    continue  # drop the opening fence line itself
                else:
                    out.append(line)
                    continue
            else:
                if skip_stack:
                    was_hidden = skip_stack.pop()
                    if was_hidden:
                        continue  # drop the matching closing fence line
                out.append(line)
                continue
        out.append(line)
    return '\n'.join(out)


def merge_chapter(chapter_dir: Path, wrapper_name: str, chapter_slug: str) -> str:
    """Read the wrapper file, resolve its {{< include LOCAL.qmd >}} calls
    (local, same-directory includes only) in order, strip old profile
    wrapping, add missing section labels, and return the merged text."""
    wrapper_path = chapter_dir / wrapper_name
    wrapper_text = wrapper_path.read_text(encoding='utf-8')
    wrapper_text = strip_profile_wrapping(wrapper_text)

    def resolve_include(m):
        target = m.group(1)
        if target.startswith('/'):
            return m.group(0)  # leave absolute/shared includes (macros etc.) as-is
        included_path = chapter_dir / target
        included_text = included_path.read_text(encoding='utf-8')
        included_text = strip_profile_wrapping(included_text)
        return included_text

    merged = INCLUDE_RE.sub(resolve_include, wrapper_text)
    merged = add_missing_labels(merged, chapter_slug)
    return merged


# ---------------------------------------------------------------------------
# Reflow / cleanup pass
# ---------------------------------------------------------------------------

MATH_OR_ATOMIC_RE = re.compile(
    r'(\$\$[^$]*\$\$|\$[^$]*\$|\[\^[^\]]+\]|\[@[^\]]+\]|\{\{<[^>]*>\}\})'
)

NON_PARAGRAPH_START_RE = re.compile(
    r'^\s*(#|:::|-{1}\s|\*\s|\+\s|>|\||`|\{\{<)'
)

INDENTED_CONTINUATION_RE = re.compile(r'^(    |\t)')

# --- ordinary (non-lproof) numbered/lettered/roman-numeral list handling ---
# Unlike lproof content, these ARE ordinary prose paragraphs from Pandoc's
# point of view, and read much better with a hanging indent: continuation
# lines wrapped to align under the item's own text rather than back to the
# left margin. Handled separately from NON_PARAGRAPH_START_RE (which now
# just passes bullets/headings/etc. through untouched) because list items
# need active reflow + recursive handling of nested sub-lists.
_ROMAN_WHITELIST = {
    'i', 'ii', 'iii', 'iv', 'v', 'vi', 'vii', 'viii', 'ix', 'x',
    'xi', 'xii', 'xiii', 'xiv', 'xv',
}
LIST_ITEM_RE = re.compile(r'^(\s*)(\(?)([a-zA-Z]+|\d+)(\)|[.)])(\.)?(\s+)(.*)$')


def _is_ordered_list_marker(letters_or_digits: str) -> bool:
    """A numeric marker (1, 2, 23, ...) is always valid. A letter marker
    is valid only if it's a single letter (a, b, ... -- an ordinary
    lettered list) or a recognized lowercase roman numeral (i, ii, iii,
    iv, ...) -- this avoids matching an ordinary word that happens to
    start a line and be followed by a period, e.g. 'The. next sentence'."""
    if letters_or_digits.isdigit():
        return True
    lowered = letters_or_digits.lower()
    if len(letters_or_digits) == 1 and letters_or_digits.isalpha():
        return True
    return lowered in _ROMAN_WHITELIST


def _line_indent(line: str) -> int:
    return len(line) - len(line.lstrip(' '))


def _is_fence_line(line: str) -> bool:
    """True for a code fence, display-math fence, div fence delimiter,
    or a Markdown thematic break (a bare '---', '***', '___', etc.).
    These always end a list region immediately, regardless of
    indentation -- and, in the main reflow loop, must never be merged
    into surrounding prose. A thematic break merged into a paragraph
    gets converted by Pandoc's smart-typography into a literal em-dash
    instead of staying a horizontal rule -- confirmed by direct
    reproduction, not a hypothetical."""
    return bool(CODE_FENCE_RE.match(line) or MATH_FENCE_RE.match(line)
                or DIV_FENCE_RE.match(line) or THEMATIC_BREAK_RE.match(line))


def _blank_gap_continues_list(lines, j, base_indent):
    """After a run of blank lines ending just before index j, decide
    whether the list region continues: yes if the next content line is
    indented strictly more than base_indent (a continuation paragraph),
    or is itself a valid sibling item at exactly base_indent. A line at
    base_indent that is NOT a list item means ordinary prose has resumed
    at the margin, so the list has ended. A fence line always ends it."""
    if j >= len(lines):
        return False
    line = lines[j]
    if _is_fence_line(line):
        return False
    indent = _line_indent(line)
    if indent > base_indent:
        return True
    if indent == base_indent:
        m = LIST_ITEM_RE.match(line)
        return bool(m and _is_ordered_list_marker(m.group(3)))
    return False


def reflow_list_region(lines, width: int):
    """Reflow one contiguous (possibly multi-paragraph, possibly nested)
    ordered-list region starting at lines[0] (which must be a valid list
    item). Consumes as many lines as belong to this list -- stopping at
    a dedent below the first item's indentation -- and returns
    (rendered_lines, number_of_input_lines_consumed); trailing lines are
    left for the caller."""
    out = []
    i = 0
    n = len(lines)
    m0 = LIST_ITEM_RE.match(lines[0])
    base_indent = len(m0.group(1))

    while i < n:
        line = lines[i]
        if _is_fence_line(line):
            break  # structural fence (e.g. a div closing) -- never list content
        if line.strip() == '':
            # blank line: only part of this region if the list continues
            # afterward at >= base_indent; otherwise this is where the
            # region (and likely the enclosing blank-line gap) ends.
            j = i
            while j < n and lines[j].strip() == '':
                j += 1
            if not _blank_gap_continues_list(lines, j, base_indent):
                break
            out.append('')
            i += 1
            continue
        indent = _line_indent(line)
        if indent < base_indent:
            break
        m = LIST_ITEM_RE.match(line)
        if m and indent == base_indent and _is_ordered_list_marker(m.group(3)):
            item_indent, open_paren, core, closer, extra_dot, spacer, first_text = m.groups()
            full_marker = open_paren + core + closer + (extra_dot or '')
            hang_col = len(item_indent) + len(full_marker) + 1
            marker_prefix = item_indent + full_marker + ' '

            body = []
            i += 1
            while i < n:
                nxt = lines[i]
                if _is_fence_line(nxt):
                    break  # structural fence -- never list content
                if nxt.strip() == '':
                    j = i
                    while j < n and lines[j].strip() == '':
                        j += 1
                    if not _blank_gap_continues_list(lines, j, base_indent):
                        break  # dedent -- this whole list region ends here
                    body.append(nxt)
                    i += 1
                    continue
                nxt_indent = _line_indent(nxt)
                if nxt_indent < base_indent:
                    break
                nxt_m = LIST_ITEM_RE.match(nxt)
                if (nxt_indent == base_indent and nxt_m
                        and _is_ordered_list_marker(nxt_m.group(3))):
                    break  # sibling item at the same level
                body.append(nxt)
                i += 1

            rendered = _render_item_body(first_text, body, hang_col, width)
            hang_prefix = ' ' * hang_col
            if rendered:
                first_out = rendered[0]
                rest = first_out[hang_col:] if first_out.startswith(hang_prefix) else first_out.lstrip()
                out.append(marker_prefix + rest)
                out.extend(rendered[1:])
            else:
                out.append(marker_prefix.rstrip())
            continue
        else:
            # not a sibling item at this level and not a deeper-indented
            # continuation we're expecting here -- region ends
            break
    return out, i


def _render_item_body(first_text, body_lines, hang_col: int, width: int):
    """Render one list item's own text plus its continuation lines.
    Splits on blank lines into paragraphs; a paragraph that starts with a
    deeper-indented list marker is instead treated as a nested sub-list
    and reflowed recursively via reflow_list_region."""
    hang_prefix = ' ' * hang_col
    out_lines = []
    blocks = []  # list of ('prose', [lines]) | ('blank',) | ('nested', [lines])
    cur_prose = [first_text] if first_text.strip() else []
    cur_nested = None

    def flush_prose():
        nonlocal cur_prose
        if cur_prose:
            blocks.append(('prose', cur_prose))
            cur_prose = []

    def flush_nested():
        nonlocal cur_nested
        if cur_nested:
            blocks.append(('nested', cur_nested))
            cur_nested = None

    for line in body_lines:
        if line.strip() == '':
            flush_prose()
            flush_nested()
            blocks.append(('blank',))
            continue
        indent = _line_indent(line)
        m = LIST_ITEM_RE.match(line)
        is_nested_start = indent > 0 and m and _is_ordered_list_marker(m.group(3))
        if is_nested_start:
            flush_prose()
            if cur_nested is None:
                cur_nested = [line]
            else:
                cur_nested.append(line)
        elif cur_nested is not None:
            cur_nested.append(line)
        else:
            cur_prose.append(line)
    flush_prose()
    flush_nested()

    for block in blocks:
        if block[0] == 'blank':
            out_lines.append('')
        elif block[0] == 'prose':
            text = ' '.join(l.strip() for l in block[1] if l.strip() != '')
            wrapped = _wrap_paragraph(text, width if width is None else max(width - hang_col, 20))
            for wl in wrapped.split('\n'):
                out_lines.append(hang_prefix + wl)
        elif block[0] == 'nested':
            rendered_nested, consumed = reflow_list_region(block[1], width)
            out_lines.extend(rendered_nested)
            leftover = block[1][consumed:]
            if leftover:
                text = ' '.join(l.strip() for l in leftover if l.strip() != '')
                if text:
                    wrapped = _wrap_paragraph(text, width if width is None else max(width - hang_col, 20))
                    for wl in wrapped.split('\n'):
                        out_lines.append(hang_prefix + wl)
    return out_lines


def _tokenize_preserving_adjacency(text: str):
    """Scan left to right. Protected spans (math/footnotes/citations/
    shortcodes) are single tokens with their REAL text and length. Any
    token directly adjacent to the previous one (no whitespace between
    them in the source -- e.g. 'valuation?[^note]' or '[^note]:') is
    merged onto it rather than getting a space inserted. This matters:
    a space wrongly inserted before a footnote definition's ':' stops
    Pandoc from recognizing it as a footnote at all."""
    spans = {m.start(): m.end() for m in MATH_OR_ATOMIC_RE.finditer(text)}
    n = len(text)
    i = 0
    prev_end = None
    merged = []  # list of str, each a "word" to place on its own wrap slot
    while i < n:
        if i in spans:
            end = spans[i]
            piece = text[i:end]
        elif text[i].isspace():
            i += 1
            prev_end = None  # whitespace breaks adjacency
            continue
        else:
            j = i
            while j < n and not text[j].isspace() and j not in spans:
                j += 1
            end = j
            piece = text[i:end]

        if prev_end == i and merged:
            merged[-1] += piece  # glued to previous token, no space
        else:
            merged.append(piece)
        prev_end = end
        i = end
    return merged


DANGEROUS_LINE_START_RE = re.compile(
    r'^(\d+[.)]|[a-zA-Z][.)]|(?:'
    + '|'.join(sorted(_ROMAN_WHITELIST, key=len, reverse=True))
    + r')[.)]|@[\w-]+\))(\s|$)'
)


def _fix_dangerous_line_starts(lines):
    """A wrapped continuation line that happens to start with something
    matching an ordered-list marker (e.g. a bare year like '1975.', or a
    Pandoc example-list ref like '@fig-x)') gets misparsed by Pandoc as
    starting a brand new list, mid-sentence -- confirmed by direct testing,
    not a hypothetical. If a candidate line would start that way, the
    offending leading token is glued onto the end of the previous line
    instead, even if that pushes it slightly past the target width;
    correctness wins over exact width here."""
    fixed = list(lines)
    i = 1
    while i < len(fixed):
        m = DANGEROUS_LINE_START_RE.match(fixed[i])
        if m and i > 0:
            token = fixed[i][:m.end(1)]
            rest = fixed[i][m.end(1):].lstrip()
            fixed[i - 1] = fixed[i - 1] + ' ' + token
            if rest:
                fixed[i] = rest
            else:
                del fixed[i]
                continue
        i += 1
    return fixed


_ABBREVIATIONS = {
    'e.g', 'i.e', 'cf', 'etc', 'vs', 'mr', 'mrs', 'ms', 'dr', 'prof', 'st',
    'vol', 'no', 'p', 'pp', 'op', 'art', 'ca', 'approx', 'resp', 'viz',
    'al', 'fig', 'eq', 'sec', 'ch', 'trans', 'ed', 'eds', 'rev',
}

SENTENCE_SPLIT_RE = re.compile(r'([.!?])([\'")\]]*)(\s+)')


def _split_sentences(text: str):
    """Split a paragraph into one chunk per sentence, for semantic-
    linebreak mode. Conservative: a candidate split is skipped if it's
    inside a protected span (math/footnote/citation/shortcode), looks
    like a decimal number, follows a recognized abbreviation, or isn't
    followed by something that looks like the start of a new sentence.
    An occasional wrong guess here is only ever cosmetic -- Pandoc
    rejoins soft-wrapped lines into the same paragraph regardless of
    where they break, so the one real risk (a line accidentally
    starting with something that looks like a new list marker) is
    handled separately by _fix_dangerous_line_starts, applied after."""
    protected = [(m.start(), m.end()) for m in MATH_OR_ATOMIC_RE.finditer(text)]

    def in_protected(pos):
        return any(s <= pos < e for s, e in protected)

    chunks = []
    last = 0
    for m in SENTENCE_SPLIT_RE.finditer(text):
        term_pos = m.start(1)
        if in_protected(term_pos):
            continue
        before = text[term_pos - 1] if term_pos > 0 else ''
        after_idx = m.end(2)
        after = text[after_idx] if after_idx < len(text) else ''
        if m.group(1) == '.' and before.isdigit() and after.isdigit():
            continue  # decimal number, e.g. '3.14'
        word_start = term_pos
        while word_start > 0 and (text[word_start - 1].isalnum() or text[word_start - 1] == '.'):
            word_start -= 1
        word = text[word_start:term_pos].lower()
        if word in _ABBREVIATIONS:
            continue
        next_start = m.end()
        nxt = text[next_start] if next_start < len(text) else ''
        if nxt and not (nxt.isupper() or nxt.isdigit() or nxt in '([{$'):
            continue
        split_at = m.end()
        chunk = text[last:split_at].strip()
        if chunk:
            chunks.append(chunk)
        last = split_at
    tail = text[last:].strip()
    if tail:
        chunks.append(tail)
    return chunks


def _wrap_paragraph(text: str, width) -> str:
    """width=None selects semantic-linebreak mode (one sentence per
    output line); an integer selects column-wrap mode at that width."""
    if width is None:
        lines = _split_sentences(text)
    else:
        tokens = _tokenize_preserving_adjacency(text)
        lines = []
        cur = []
        cur_len = 0
        for tok in tokens:
            add_len = len(tok) + (1 if cur else 0)
            if cur and cur_len + add_len > width:
                lines.append(' '.join(cur))
                cur = [tok]
                cur_len = len(tok)
            else:
                cur.append(tok)
                cur_len += add_len
        if cur:
            lines.append(' '.join(cur))
    lines = _fix_dangerous_line_starts(lines)
    return '\n'.join(lines)


def reflow(text: str, width: int = 90) -> str:
    lines = text.split('\n')

    # Pass through a leading YAML frontmatter block (--- ... ---) verbatim;
    # it's structured metadata, not prose, and must never be reflowed.
    front_matter = []
    if lines and lines[0].strip() == '---':
        front_matter.append(lines[0])
        i = 1
        while i < len(lines):
            front_matter.append(lines[i])
            if lines[i].strip() == '---':
                i += 1
                break
            i += 1
        lines = lines[i:]

    out = []
    tracker = FenceTracker()
    para_buf = []

    def flush_para():
        if para_buf:
            joined = ' '.join(l.strip() for l in para_buf)
            out.append(_wrap_paragraph(joined, width))
            para_buf.clear()

    prev_blank = None  # None = start of file (don't force a leading blank)
    i = 0
    n = len(lines)
    while i < n:
        raw_line = lines[i]
        line = raw_line.rstrip()
        is_fence = tracker.consume(line)

        if is_fence:
            flush_para()
            out.append(raw_line)
            prev_blank = False
            i += 1
            continue

        if THEMATIC_BREAK_RE.match(line):
            # a bare '---'/'***'/'___' horizontal rule -- merging this
            # into a paragraph (as ordinary reflow would) makes Pandoc's
            # smart-typography extension convert it into a literal em-dash
            # instead of keeping it a horizontal rule. Confirmed by direct
            # reproduction, not a hypothetical.
            flush_para()
            out.append(raw_line)
            prev_blank = False
            i += 1
            continue

        if tracker.in_protected_block():
            # inside code, display-math, or an .lproof div: pass through
            # completely untouched, not even trailing-whitespace trimmed --
            # lproof in particular parses its content as raw text (exact
            # indentation and line numbers matter), so nothing here may
            # be rejoined, rewrapped, or trimmed.
            flush_para()
            out.append(raw_line)
            prev_blank = (line.strip() == '')
            i += 1
            continue

        if line.strip() == '':
            flush_para()
            if prev_blank is False or prev_blank is None:
                out.append('')
            prev_blank = True
            i += 1
            continue

        list_m = LIST_ITEM_RE.match(line)
        if list_m and _is_ordered_list_marker(list_m.group(3)):
            # ordinary numbered/lettered/roman list item: reflow with a
            # hanging indent (much more readable than a raw, unwrapped
            # source line), recursing into any nested sub-list.
            flush_para()
            rendered, consumed = reflow_list_region(lines[i:], width)
            out.extend(rendered)
            prev_blank = (rendered[-1].strip() == '') if rendered else prev_blank
            i += consumed
            continue

        if NON_PARAGRAPH_START_RE.match(line):
            flush_para()
            out.append(raw_line)
            prev_blank = False
            i += 1
            continue

        if INDENTED_CONTINUATION_RE.match(raw_line):
            # 4-space/tab indented line: a footnote or list-item
            # continuation paragraph. Pandoc requires this exact
            # indentation to keep it attached to its parent block --
            # stripping it (as normal reflow would) silently detaches
            # the paragraph, turning it into ordinary inline text.
            # Left untouched rather than risk corrupting it.
            flush_para()
            out.append(raw_line)
            prev_blank = False
            i += 1
            continue

        # plain paragraph text -- accumulate for reflow
        para_buf.append(line)
        prev_blank = False
        i += 1

    flush_para()

    # collapse any remaining runs of 2+ blank lines to exactly 1
    cleaned = []
    for line in out:
        if line == '' and cleaned and cleaned[-1] == '':
            continue
        cleaned.append(line)
    body = '\n'.join(cleaned).strip() + '\n'

    if front_matter:
        return '\n'.join(front_matter) + '\n\n' + body
    return body


if __name__ == '__main__':
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description='Reflow .qmd files in place (semantic-linebreak mode '
                    'by default). Used both as a pre-commit hook and, in '
                    '--check mode, as a CI gate.'
    )
    parser.add_argument('paths', nargs='+', help='Paths to .qmd files to reflow')
    parser.add_argument('--width', type=int, default=None,
                         help='Column-wrap width. Omit for semantic-'
                              'linebreak mode (one sentence per line).')
    parser.add_argument('--check', action='store_true',
                         help="Don't modify files; exit nonzero if any "
                              "file is not already correctly formatted.")
    args = parser.parse_args()

    needs_changes = []
    for path_str in args.paths:
        p = Path(path_str)
        original = p.read_text(encoding='utf-8')
        updated = reflow(original, width=args.width)
        if updated != original:
            needs_changes.append(str(p))
            if not args.check:
                p.write_text(updated, encoding='utf-8')

    if needs_changes:
        verb = 'would be reflowed' if args.check else 'reflowed'
        print(f'The following files {verb} (semantic linebreaks):')
        for c in needs_changes:
            print(f'  {c}')
        if not args.check:
            print('Please review and re-stage these changes, then commit again.')
        sys.exit(1)
    sys.exit(0)
