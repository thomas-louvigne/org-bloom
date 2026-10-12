# 🌸 org-bloom

**The org-mode static website-builder. Works with [Logseq](https://logseq.com/) & [Orgamnesia](https://github.com/thomas-louvigne/orgamnesia).**

Turns a folder of notes into a static website — HTML + CSS + vanilla JS, no server, no build framework. One tool for every org-mode knowledge base:

| Works with | What it reads |
|---|---|
| 🦄 **Emacs org-mode** | any folder of `.org` files, subfolders included: `#+TITLE`, `#+DATE`, `#+AUTHOR`, `#+FILETAGS`, headline tags, timestamps, `:noexport:`, `file:` links… |
| 🧠 **[org-roam](https://www.orgroam.com/)** | `[[id:…]]` links (file and headline IDs), `daily/` notes as blog posts |
| 🪵 **[Logseq](https://logseq.com/)** | graphs in Org **or Markdown**, as before: `[[Page]]`, `#tags`, `tags::`, journals, `logseq/config.edn` settings |
| 🌱 **[Orgamnesia](https://github.com/thomas-louvigne/orgamnesia)** | its projects as is, and its Export button (`org-bloom build <project>`) |

Logseq compatibility is kept: a Logseq graph builds the same pages as with `logseq-site-builder`, with tag pages and readable dates on top.

> 📛 **org-bloom was previously called `logseq-site-builder`** — see [Coming from logseq-site-builder](#coming-from-logseq-site-builder).

> 🤖 **Vibecoded** — entirely generated through vibe coding with Claude. Readable and hackable, but still **early beta**: expect rough edges and breaking changes.

## Example

[chroniques-insoumises.com](https://chroniques-insoumises.com/) — a Logseq knowledge base built with the `nord` theme.

## Themes

![The default, dark and nord built-in themes, rendered from the sample sites in test-sites/](docs/themes.png)

Three built-in themes — `default`, `dark` and `nord` — or bring your own CSS. The optional **tree view** (`tree_view = true`, shown on `default` and `nord` above) draws guide lines between nested bullets and makes every branch foldable; turn it off for classic bullets (`dark` above). Every page also gets a **share & print bar** under its title (or pinned to the right edge with `layout = "vertical"`); each button can be switched off from the `[share]` table of the TOML.

## Features

- **Logseq graphs, Emacs org-mode folders and Orgamnesia projects** — see [Project types](#project-types)
- **Org & Markdown** pages, converted via Pandoc
- **Selective publishing** — `#+PUBLIC: true` per page, an all-public mode with `#+PUBLIC: false` / `:noexport:` exclusions, or hide specific paths
- **Wiki links, images & attachments** handled automatically (`[[Page]]`, `[[../assets/file.pdf]]`…)
- **Org-mode links** — `[[file:page.org]]`, `[[file:page.org::*Headline]]`, `[[id:…]]` (org-roam style), `[[*Headline]]`, `[[#custom-id]]`, and files linked next to a page (`[[file:docs/guide.pdf]]`)
- **Blog / journals** — index page + RSS feed generated from your Logseq journals or org-roam dailies, with `#+TITLE`, `#+DATE` and `#+AUTHOR`
- **Tags** — `#+FILETAGS`, headline tags (`* Title :a:b:`) and Logseq `tags::` shown as links, with one page per tag listing the pages and headlines that carry it
- **Dates** — org timestamps (`<2026-10-12 Mon 10:00>`, `[2026-10-11 Sun]`) written out in the site's language; a page's `#+DATE` and `#+AUTHOR` shown under its title
- **Themes** — built-in `default`, `dark` and `nord`, or bring your own CSS
- **Tree view** — optional guide lines and fold/unfold buttons on nested bullets
- **Nav menu & social links**, configurable via TOML
- **Custom HTML/CSS pages** copied as-is (embeds, mini-apps, slide decks…)
- **External static sites** — copy in mini-sites that live outside the project (`[[external_static_dirs]]`)
- **Share & print** — share buttons on every page (WhatsApp, Facebook, X, Bluesky, LinkedIn, e-mail, copy link, native share sheet on mobile), each one switchable in `[share]`, as a row under the title or a vertical column on the right (`layout = "vertical"`); a clean print view without the menu, ending with the site title and address
- **Random page** — a nav menu entry with `random = true` links to a random published page, under the `label` you give it
- **Full-text search**, client-side (Fuse.js), no server needed
- `--check-links` to catch broken wiki links before they 404
- `--check-assets` to list assets that no page references
- `--zip` to archive the built site

## Requirements

- Python 3.11+
- [pandoc](https://pandoc.org/installing.html)

## Install

```bash
git clone https://github.com/thomas-louvigne/org-bloom.git
cd org-bloom
python -m venv .venv
source .venv/bin/activate   # .venv\Scripts\activate on Windows
pip install -e .
```

## Usage

```bash
org-bloom ~/my-notes ~/Sites/my-site
```

The output folder can also be set once, as `output_dir` in the `[site]` table of `org-bloom.toml` (relative to the project); `org-bloom ~/my-notes` then builds there. `org-bloom build ~/my-notes` works too — that is how Orgamnesia's Export button calls it.

⚠️ The output directory is **wiped** before every build — point it at a folder that holds nothing but the generated site. org-bloom refuses a folder that contains the project itself.

On first run, a `org-bloom.toml` is generated at the root of your project. Edit it to set the title, theme, nav menu, blog, RSS, etc. — see [`org-bloom.example.toml`](org-bloom.example.toml) for every option, documented.

**Logseq settings are imported.** For a Logseq graph, the generated `org-bloom.toml` is pre-filled from `logseq/config.edn`: home page (`:default-home`), all-pages-public (`:publishing/all-pages-public?`), hidden paths (`:hidden`), pages and journals folders, journals on/off and their date formats. `config.edn` is also read on every build for any key the TOML leaves out, so the graph keeps working even without a TOML.

Priority: CLI options > TOML file > `logseq/config.edn`.

### Project types

org-bloom looks for a `logseq/` folder at the root of the project:

| | Logseq graph (has `logseq/`) | Org-mode project (Emacs, Orgamnesia) |
|---|---|---|
| Pages read | `.org` and `.md` in `pages/` | `.org` in `pages/` (or the folder itself), **subfolders included** — except hidden ones (`.trash`, `.git`…), `assets/`, the journals and the output folder |
| Published | pages with `#+PUBLIC: true` (or `all_public = true`) | **every page**, except those with `#+PUBLIC: false` or `#+FILETAGS: :noexport:` (`all_public = false` restores the opt-in rule) |
| `*` headlines | the deepest level becomes bullets, like Logseq (`org_listify_headings_from = "auto"`) | **real headings**, like an Emacs export (`org_listify_headings_from = false`) |
| Title headline | kept | see below |
| Blog date format | `journal_page_title_format` (`dd-MM-yyyy`) | written out in `lang` (`12 octobre 2026`) |

Two pages with the same title in different subfolders get distinct URLs (the second one is named after its path).

**Title headline.** Every page of the site shows its title in large type at the top. Orgamnesia starts a new page `Élody.org` with the line `* Élody`, so that title would appear twice in a row. In an org-mode project, a first `* Headline` that only repeats the page name (or its `#+TITLE`) is therefore not shown; any other headline is kept.

### Keeping notes private: `noexport`

The `noexport` tag keeps a note out of the site, whatever the publishing mode:

| | To hide a whole page | To hide part of a page |
|---|---|---|
| Emacs org-mode, org-roam, Orgamnesia | `#+FILETAGS: :noexport:` | tag the headline: `* Brouillon :noexport:` — the headline and everything under it are left out |
| Logseq, Org page | `#+filetags: :noexport:` (what Logseq writes when you add the `noexport` tag to the page) | same as Emacs: `* Brouillon :noexport:` |
| Logseq, Markdown page | `tags:: noexport` in the first block (the page properties) | — |

`#+PUBLIC: false` (Org) or `public:: false` (Markdown) also keep a page private when every page is published.

### Folders that are not read

In an org-mode project, subfolders are read, except:

- hidden folders, whose name starts with a dot: `.trash` (Orgamnesia and Logseq trash), `.git`, `.obsidian`…
- `assets/` (files are copied only when a page links them) and `logseq/`;
- the journals folder (`journals/` or `daily/`), read as the blog instead;
- the output folder, when it sits inside the project.

To leave out more folders or files, list them in `hidden`, relative to the project root:

```toml
[site]
hidden = ["/archives", "/pages/drafts", "/pages/secret.org"]
```

A Logseq graph fills `hidden` from `:hidden` in `logseq/config.edn`.

### org-roam

org-roam links by ID: `[[id:2f0c…][Label]]` leads to the page whose file-level `:PROPERTIES:` drawer has that `:ID:`, or to the headline whose drawer has it. An ID that matches no published page is reported by `--check-links` and its label shown as plain text. Daily notes in `daily/` (`2026-10-12.org`) become the blog when `enable_journals = true`.

### Blog, dates and authors

The blog is built from the journals folder — `journals/` (Logseq) or `daily/` (org-roam) — once `enable_journals = true`. Journal files are named after their date: `journal_file_name_format` (Logseq's `yyyy_MM_dd`), `2026-10-12` (org-roam) or `20261012` (org-journal). In each post:

- `#+TITLE:` gives the post its title (otherwise its date does);
- `#+DATE:` gives its date (otherwise the file name does);
- `#+AUTHOR:` is shown under the title, in the blog list and as the RSS `dc:creator`. **No `#+AUTHOR`, no author shown.**

Ordinary pages show their `#+DATE` and `#+AUTHOR` under the title too, when they have them. Logseq Markdown pages can use `date::` and `author::`.

Org timestamps in the text — `<2026-10-12 Mon>`, `[2026-10-11 Sun 10:00]`, ranges and repeaters — are written out in the site's `lang` (`12 octobre 2026 à 10:00`, `October 11, 2026, 10:00`; other languages: ISO dates). Code blocks are left alone.

### Tags

Page tags (`#+FILETAGS: :a:b:`, Logseq's `tags::`) are shown under the page title, and headline tags (`* Title :a:b:`) next to the headline, as links. Each tag gets a page, `tag-<name>.html`, listing the pages and headlines that carry it, with a link to the page of the same name when there is one. `noexport` is never shown.

### Options

| Option | Description |
|---|---|
| `--site-title TEXT` | Site title (default: directory name) |
| `--home-page SLUG` | Page to use as `index.html` |
| `--all-public` | Publish all pages, ignore `#+PUBLIC` |
| `--social NAME:URL` | Social link in the nav menu (repeatable) |
| `--theme NAME_OR_PATH` | `default`, `dark`, `nord`, or a path to a CSS file |
| `--check-links` | List internal links that would 404 |
| `--check-assets` | List assets that no page references |
| `--zip` | Zip the built site into `<output_dir>.zip` |
| `--no-init-toml` | Skip generating the TOML on first run |

### Preview locally

```bash
cd ~/Sites/my-site
python3 -m http.server 8080
```

## Coming from logseq-site-builder

org-bloom is the new name of `logseq-site-builder`. What changed:

| Before | Now |
|---|---|
| repository `thomas-louvigne/logseq-site-builder` | [`thomas-louvigne/org-bloom`](https://github.com/thomas-louvigne/org-bloom) (GitHub redirects the old URL) |
| `logseq-builder` command | `org-bloom` |
| `logseq-site-builder.toml` | `org-bloom.toml` |
| Python package `logseq_builder` | `org_bloom` |

Your existing `logseq-site-builder.toml` keeps working: it is read whenever no `org-bloom.toml` sits next to it. Rename it to `org-bloom.toml` when convenient. To swap the old command for the new one, run `pip uninstall logseq-site-builder` then `pip install -e .` from this repository.

## Tests

```bash
pip install -e ".[dev]"
python3 -m pytest
```
