#!/usr/bin/env python3
"""Bring what the site shows from the repository into site/: the user
guides (docs/user/*.md) as pages of content/guide/, the pictures
(docs/images/*.png) under static/images/, and the icon. The guides are
written to read on GitHub; here each gets front matter, its title taken
from its first heading, and its links made the site's: another guide by
Zola's @/ path, a picture relative to the page, any other document of the
repository on GitHub. Run before `zola build` or `zola serve`; what it
writes is not kept in git."""

import re
import shutil
from pathlib import Path

SITE = Path(__file__).resolve().parent
ROOT = SITE.parent
GUIDES = ROOT / "docs" / "user"
IMAGES = ROOT / "docs" / "images"
REPO = "https://github.com/gilramir/puritty/blob/main/"

# the guide's order; a guide not named here comes after these
ORDER = ["getting-started", "settings", "fonts", "copy-and-paste", "tabs", "tmux", "diagnostics"]


def link(m):
    text, target = m.group(1), m.group(2)
    if re.match(r"[a-z]+:", target) or target.startswith("#"):
        return m.group(0)
    path, _, anchor = target.partition("#")
    anchor = "#" + anchor if anchor else ""
    if path.startswith("../images/"):
        return f"[{text}](../../images/{path[len('../images/'):]}{anchor})"
    if "/" not in path and path.endswith(".md") and (GUIDES / path).exists():
        return f"[{text}](@/guide/{path}{anchor})"
    # another document of the repository: on GitHub
    return f"[{text}]({REPO}{(Path('docs/user') / path).as_posix().replace('docs/user/../', 'docs/')}{anchor})"


def guide(src, weight):
    lines = src.read_text().splitlines()
    title = next((l[2:].strip() for l in lines if l.startswith("# ")), src.stem)
    body = "\n".join(l for l in lines if not l.startswith("# ")).strip() + "\n"
    body = re.sub(r"(?<!!)\[([^\]]*)\]\(([^)\s]+)\)", link, body)
    body = re.sub(r"!\[([^\]]*)\]\(\.\./images/([^)\s]+)\)", r"![\1](../../images/\2)", body)
    front = f'+++\ntitle = "{title}"\nweight = {weight}\n[extra]\nsource = "docs/user/{src.name}"\n+++\n\n'
    (SITE / "content" / "guide" / src.name).write_text(front + body)


def main():
    out = SITE / "content" / "guide"
    for old in out.glob("*.md"):
        if old.name != "_index.md":
            old.unlink()
    names = sorted(GUIDES.glob("*.md"), key=lambda p: (ORDER.index(p.stem) if p.stem in ORDER else len(ORDER), p.stem))
    for i, src in enumerate(names):
        guide(src, i + 1)
    images = SITE / "static" / "images"
    images.mkdir(parents=True, exist_ok=True)
    for png in IMAGES.glob("*.png"):
        shutil.copy2(png, images / png.name)
    for size in (32, 64, 256):
        shutil.copy2(ROOT / "app" / "icon" / "png" / f"{size}.png", SITE / "static" / f"icon-{size}.png")
    shutil.copy2(ROOT / "app" / "icon" / "puritty.ico", SITE / "static" / "favicon.ico")
    print(f"{len(names)} guides, {len(list(IMAGES.glob('*.png')))} pictures")


if __name__ == "__main__":
    main()
