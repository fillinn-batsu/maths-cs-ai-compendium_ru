#!/usr/bin/env python3
"""Structural QA for the RU translation.

Compares each translated file against its English original and reports any
divergence in the parts that MUST stay identical: LaTeX, image targets, code,
heading/bullet/table counts. Meaning is reviewed separately; this catches the
mechanical failures (dropped paragraph, translated variable name, broken link).

usage: check_translation.py <original_repo> <translated_repo> [relative/path.md ...]
"""
import re
import sys
from pathlib import Path

FENCE = re.compile(r"^```(\w*)\s*$")
IMG = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
DISPLAY_MATH = re.compile(r"\$\$(.+?)\$\$", re.S)
INLINE_MATH = re.compile(r"(?<!\$)\$([^$\n]+)\$(?!\$)")
HEADING = re.compile(r"^(#{1,6})\s", re.M)
BULLET = re.compile(r"^\s*[-*]\s", re.M)
TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$", re.M)
# 3+ consecutive latin words = probably an untranslated sentence
LATIN_RUN = re.compile(r"(?:\b[A-Za-z][a-z]{2,}\b[ ,]+){2}\b[A-Za-z][a-z]{2,}\b")


def split_code(text):
    """Return (prose, [(lang, block)]) so each is checked by its own rules."""
    prose, blocks, cur, lang, inside = [], [], [], "", False
    for line in text.splitlines():
        m = FENCE.match(line)
        if m:
            if inside:
                blocks.append((lang, "\n".join(cur)))
                cur = []
            else:
                lang = m.group(1)
            inside = not inside
            continue
        (cur if inside else prose).append(line)
    return "\n".join(prose), blocks


def strip_comments(code):
    """Code must match exactly, except comments — those are prose and translated."""
    out = []
    for line in code.splitlines():
        line = re.sub(r"#.*$", "", line).rstrip()
        if line:
            out.append(line)
    return "\n".join(out)


def norm_math(expr):
    return re.sub(r"\\(?:text|mathrm|textrm)\{[^}]*\}", r"\\text{}", expr.strip())


def check(rel, src, dst):
    issues = []
    o, t = src.read_text(), dst.read_text()
    o_prose, o_code = split_code(o)
    t_prose, t_code = split_code(t)

    o_imgs, t_imgs = IMG.findall(o), IMG.findall(t)
    if o_imgs != t_imgs:
        issues.append(f"image targets differ: {set(o_imgs) ^ set(t_imgs)}")

    for name, rx in (("display math", DISPLAY_MATH), ("inline math", INLINE_MATH)):
        a, b = rx.findall(o_prose), rx.findall(t_prose)
        na, nb = [norm_math(x) for x in a], [norm_math(y) for y in b]
        if len(a) != len(b):
            issues.append(f"{name} count {len(a)} -> {len(b)}")
        elif na != nb:
            # Word order differs between English and Russian, so a formula may
            # legitimately move within its sentence. Only a changed *set* is a bug.
            if sorted(na) == sorted(nb):
                pass
            else:
                for x, y in zip(na, nb):
                    if x != y:
                        issues.append(f"{name} changed: {x!r} -> {y!r}")

    for name, rx in (("headings", HEADING), ("bullets", BULLET), ("table rows", TABLE_ROW)):
        a, b = len(rx.findall(o_prose)), len(rx.findall(t_prose))
        if a != b:
            issues.append(f"{name} count {a} -> {b}")

    if len(o_code) != len(t_code):
        issues.append(f"code blocks {len(o_code)} -> {len(t_code)}")
    else:
        for i, ((la, a), (lb, b)) in enumerate(zip(o_code, t_code), 1):
            # ```math fences are formulas, not code: only \text{} may change.
            same = norm_math(a) == norm_math(b) if la == "math" else strip_comments(a) == strip_comments(b)
            if la != lb or not same:
                issues.append(f"code block {i} modified beyond comments")

    for m in LATIN_RUN.finditer(t_prose):
        issues.append(f"possibly untranslated: {m.group(0)!r}")

    return issues


def main():
    orig, trans = Path(sys.argv[1]), Path(sys.argv[2])
    rels = sys.argv[3:] or [
        str(p.relative_to(trans)) for p in sorted(trans.glob("chapter */*.md"))
    ]
    bad = 0
    for rel in rels:
        src, dst = orig / rel, trans / rel
        if not src.exists():
            print(f"?? {rel}: no original")
            continue
        if dst.read_text() == src.read_text():
            print(f"-- {rel}: not translated yet")
            continue
        issues = check(rel, src, dst)
        if issues:
            bad += 1
            print(f"FAIL {rel}")
            for i in issues:
                print(f"     - {i}")
        else:
            print(f"OK   {rel}")
    print(f"\n{bad} file(s) with structural issues")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
