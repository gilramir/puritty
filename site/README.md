# puritty's website

The site at https://gilramir.github.io/puritty/, built with
[Zola](https://www.getzola.org) 0.23.6 and published by
`.github/workflows/pages.yml` on each push to `main` that changes it.

- The home page is `content/_index.md` (its words are in the front matter,
  laid out by `templates/index.html`); the roadmap is `content/roadmap.md`.
- The guide's pages are the user guides in `docs/user/`, which read on
  GitHub too. `sync.py` copies them into `content/guide/` with front matter,
  and the pictures in `docs/images/` and the icon into `static/`; nothing
  it writes is kept in git. The guide's order is `ORDER` in `sync.py`.

To look at it locally:

```sh
python3 site/sync.py
cd site && zola serve       # http://127.0.0.1:1111
```
