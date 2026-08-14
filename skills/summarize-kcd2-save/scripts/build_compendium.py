#!/usr/bin/env python3
"""Build a compact multi-page KCD2 save compendium from vetted narrative JSON."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from html import escape
from pathlib import Path
from typing import Any


PAGES = ("index.html", "chronicle.html", "people.html", "henry.html", "checkpoint.html")
SAFE_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class CompendiumError(RuntimeError):
    pass


def h(value: Any) -> str:
    return escape(str(value), quote=True)


def required(obj: dict[str, Any], key: str, kind: type | tuple[type, ...]) -> Any:
    if key not in obj or not isinstance(obj[key], kind):
        names = kind.__name__ if isinstance(kind, type) else "/".join(x.__name__ for x in kind)
        raise CompendiumError(f"{key!r} is required and must be {names}")
    return obj[key]


def validate_content(data: dict[str, Any]) -> None:
    for key in ("title", "subtitle", "spoiler_boundary", "confidence"):
        required(data, key, str)
    required(data, "summary", list)
    save = required(data, "save", dict)
    for key in ("quest", "objective", "position", "region", "build", "save_type", "background", "last_result", "source_note"):
        required(save, key, str)
    chronicle = required(data, "chronicle", list)
    if not chronicle:
        raise CompendiumError("chronicle must contain at least one evidenced event")
    seen_ids: set[str] = set()
    for index, event in enumerate(chronicle):
        if not isinstance(event, dict):
            raise CompendiumError(f"chronicle[{index}] must be an object")
        event_id = required(event, "id", str)
        if not SAFE_ID.fullmatch(event_id) or event_id in seen_ids:
            raise CompendiumError(f"chronicle[{index}].id must be unique kebab-case")
        seen_ids.add(event_id)
        for key in ("label", "title"):
            required(event, key, str)
        required(event, "paragraphs", list)
        if "objectives" in event and not isinstance(event["objectives"], list):
            raise CompendiumError(f"chronicle[{index}].objectives must be an array")
    people = required(data, "people", dict)
    for group in ("encountered", "discussed"):
        for index, person in enumerate(required(people, group, list)):
            if not isinstance(person, dict):
                raise CompendiumError(f"people.{group}[{index}] must be an object")
            person_id = required(person, "id", str)
            if not SAFE_ID.fullmatch(person_id) or person_id in seen_ids:
                raise CompendiumError(f"people.{group}[{index}].id must be unique kebab-case")
            seen_ids.add(person_id)
            for key in ("name", "role", "summary"):
                required(person, key, str)
            if group == "encountered":
                required(person, "initials", str)
    required(data, "politics", list)
    henry = required(data, "henry", dict)
    for key in ("profile", "traits", "choices"):
        required(henry, key, list)
    resume = required(data, "resume", dict)
    for key in ("what_doing", "just_happened", "next_action"):
        required(resume, key, str)
    required(resume, "known_state", list)


def paragraphs(values: list[Any], class_name: str = "") -> str:
    attr = f' class="{h(class_name)}"' if class_name else ""
    return "".join(f"<p{attr}>{h(value)}</p>" for value in values)


def search_index(data: dict[str, Any]) -> list[dict[str, str]]:
    entries = [
        {"title": data["title"], "note": "Overview and current status", "url": "index.html", "tags": f"overview {data['save']['quest']} {data['save']['objective']}"},
        {"title": "Recorded choices", "note": "This playthrough’s decisions", "url": "henry.html#choices", "tags": " ".join(data["henry"]["traits"])},
        {"title": data["save"]["position"], "note": "Current stopping point", "url": "checkpoint.html", "tags": f"{data['save']['quest']} {data['save']['objective']} {data['save']['region']}"},
    ]
    for event in data["chronicle"]:
        entries.append({"title": event["title"], "note": event["label"], "url": f"chronicle.html#{event['id']}", "tags": " ".join(event.get("objectives", []))})
    for person in data["people"]["encountered"] + data["people"]["discussed"]:
        entries.append({"title": person["name"], "note": person["role"], "url": f"people.html#{person['id']}", "tags": person["summary"]})
    return entries


def sidebar(active: str, data: dict[str, Any], local_links: list[tuple[str, str]] | None = None) -> str:
    pages = (
        ("index.html", "⌂", "Overview", "index"),
        ("chronicle.html", "Ⅰ", "Chronicle", "chronicle"),
        ("people.html", "♟", "People & powers", "people"),
        ("henry.html", "⚔", "Your Henry", "henry"),
        ("checkpoint.html", "◆", "Current checkpoint", "checkpoint"),
    )
    nav = "".join(
        f'<a href="{url}"{(" aria-current=\"page\"" if key == active else "")}><span class="nav-icon">{icon}</span>{label}</a>'
        for url, icon, label, key in pages
    )
    local = ""
    if local_links:
        items = "".join(f'<a href="#{h(anchor)}"><span class="nav-icon">→</span>{h(label)}</a>' for anchor, label in local_links)
        local = f'<p class="nav-label">In this article</p><nav class="side-nav">{items}</nav>'
    return f'''<aside class="sidebar" id="sidebar" aria-label="Compendium navigation"><div class="sidebar-inner">
      <a class="wordmark" href="index.html"><img src="assets/kcd2-logo.png" alt="Kingdom Come: Deliverance II"></a>
      <p class="edition">Personal save compendium</p><div class="save-state">At {h(data["save"]["position"])} · {h(data["save"]["quest"])}</div>
      <div class="search"><label for="compendium-search">Search the compendium</label><input id="compendium-search" type="search" placeholder="Search entries" autocomplete="off" aria-expanded="false" aria-controls="search-results"><div class="search-results" id="search-results" role="listbox"></div></div>
      <p class="nav-label">Compendium</p><nav class="side-nav">{nav}</nav>{local}
      <p class="sidebar-note">Spoiler-safe edition. Entries stop at the latest objective evidenced in the save.</p>
    </div></aside>'''


def document(active: str, title: str, entry: str, lede: str, data: dict[str, Any], body: str, local_links: list[tuple[str, str]] | None = None) -> str:
    index_json = json.dumps(search_index(data), ensure_ascii=False).replace("</", "<\\/")
    return f'''<!doctype html><html lang="en"><head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="description" content="{h(lede)}">
  <title>{h(title)} — KCD2 Save Compendium</title><link rel="stylesheet" href="assets/styles.css">
  <script>window.COMPENDIUM_INDEX={index_json};</script><script src="assets/site.js" defer></script>
</head><body>
  <a class="skip-link" href="#content">Skip to article</a><div class="mobilebar"><button type="button" data-menu-toggle aria-expanded="false" aria-controls="sidebar" aria-label="Open compendium navigation">☰</button><strong>Save Compendium</strong><span aria-hidden="true">II</span></div><div class="overlay" data-overlay></div>
  {sidebar(active, data, local_links)}
  <div class="shell"><main class="page" id="content"><p class="crumbs"><a href="index.html">Save compendium</a> / {h(title)}</p>
    <header class="article-header"><div><h1>{h(title)}</h1><p class="lede">{h(lede)}</p></div><span class="page-mark">Entry {h(entry)}</span></header>
    {body}
    <footer class="page-footer"><p><strong>Personal save compendium.</strong> {h(data["save"]["source_note"])}</p><p>Unofficial fan-made reference.</p></footer>
  </main></div></body></html>'''


def quest_strip(data: dict[str, Any]) -> str:
    save = data["save"]
    return f'''<div class="quest-strip"><span class="quest-mark" aria-hidden="true">◆</span><div><strong>{h(save["objective"])}</strong><p>{h(save["quest"])} · {h(save["position"])} · {h(save["region"])}</p></div><a href="checkpoint.html">Open checkpoint →</a></div>'''


def render_index(data: dict[str, Any]) -> str:
    save = data["save"]
    summary = paragraphs(data["summary"], "standfirst")
    cards = (
        ("chronicle.html", "Chronology", "Chronicle", "Major events and confirmed quest progress."),
        ("people.html", "Reference", "People & powers", "Encountered characters and discussed political figures."),
        ("henry.html", "Playthrough", "Your Henry", "Build, dialogue posture and confirmed outcomes."),
        ("checkpoint.html", "Resume guide", "Current checkpoint", "Where you are, what you know and what to do next."),
    )
    card_html = "".join(f'<a class="index-card" href="{url}"><span class="index-type">{kind}</span><h2>{label}</h2><p>{text}</p></a>' for url, kind, label, text in cards)
    body = f'''{quest_strip(data)}<div class="wiki-layout" style="margin-top:1rem"><div class="article-stack">
      <article class="panel"><h2>Summary</h2>{summary}</article>
      <div class="notice"><span class="notice-icon">✓</span><div><strong>Current safe boundary</strong><p>{h(data["spoiler_boundary"])}</p></div></div>
      <section><h2 style="font-size:1.25rem;margin:1rem 0 .65rem">Browse the compendium</h2><div class="index-grid">{card_html}</div></section>
    </div><aside class="infobox"><div class="infobox-title"><strong>Current save</strong><span>{h(save["save_type"])}</span></div><div class="infobox-art"><span class="sigil">KCD<br>II</span></div><dl class="facts">
      <div><dt>Quest</dt><dd>{h(save["quest"])}</dd></div><div><dt>Position</dt><dd>{h(save["position"])}</dd></div><div><dt>Region</dt><dd>{h(save["region"])}</dd></div><div><dt>Henry</dt><dd>{h(save["background"])}</dd></div><div><dt>Last result</dt><dd>{h(save["last_result"])}</dd></div><div><dt>Build</dt><dd>{h(save["build"])}</dd></div>
    </dl><p class="infobox-note">{h(save["source_note"])}</p></aside></div>'''
    return document("index", data["title"], "00", data["subtitle"], data, body)


def render_chronicle(data: dict[str, Any]) -> str:
    events = []
    for event in data["chronicle"]:
        objectives = ""
        if event.get("objectives"):
            objectives = '<ul class="objective-list">' + "".join(f"<li>{h(item)}</li>" for item in event["objectives"]) + "</ul>"
        events.append(f'<section class="event" id="{h(event["id"])}"><div class="event-side">{h(event["label"])}</div><div class="event-body"><h3>{h(event["title"])}</h3>{paragraphs(event["paragraphs"])}{objectives}</div></section>')
    links = [(event["id"], event["title"]) for event in data["chronicle"]]
    body = f'''<div class="wiki-layout"><div class="article-stack"><article class="panel timeline">{"".join(events)}</article><div class="notice"><span class="notice-icon">✓</span><div><strong>Evidence boundary</strong><p>{h(data["spoiler_boundary"])}</p></div></div></div>
      <aside class="infobox"><div class="infobox-title"><strong>Chronology</strong><span>Opening → current objective</span></div><div class="infobox-art"><span class="sigil">I—V</span></div><dl class="facts"><div><dt>Events</dt><dd>{len(events)}</dd></div><div><dt>Current quest</dt><dd>{h(data["save"]["quest"])}</dd></div><div><dt>Current place</dt><dd>{h(data["save"]["position"])}</dd></div><div><dt>Next action</dt><dd>{h(data["save"]["objective"])}</dd></div></dl><p class="infobox-note">No event after the current objective is included.</p></aside></div>'''
    return document("chronicle", "Chronicle", "01", "The evidenced sequence of major events up to the current checkpoint.", data, body, links)


def render_people(data: dict[str, Any]) -> str:
    encountered = "".join(
        f'<article class="person-card" id="{h(person["id"])}"><span class="portrait">{h(person["initials"])}</span><div><h2>{h(person["name"])}</h2><p class="role">{h(person["role"])}</p><p>{h(person["summary"])}</p></div></article>'
        for person in data["people"]["encountered"]
    )
    discussed = "".join(
        f'<div id="{h(person["id"])}"><dt>{h(person["name"])}</dt><dd><strong>{h(person["role"])}</strong><br>{h(person["summary"])}</dd></div>'
        for person in data["people"]["discussed"]
    )
    politics = "".join(
        f'<tr><td><strong>{h(row.get("group", ""))}</strong></td><td>{h(row.get("figures", ""))}</td><td>{h(row.get("knowledge", ""))}</td></tr>'
        for row in data["politics"]
    )
    links = [(person["id"], person["name"]) for person in data["people"]["encountered"][:4]]
    body = f'''<div class="notice"><span class="notice-icon">i</span><div><strong>Reading this list</strong><p>Encountered figures have direct scene or journey evidence. Discussed figures are part of the mission’s known context.</p></div></div>
      <section id="encountered"><h2 style="font-size:1.35rem;margin:1rem 0 .6rem">Encountered or present</h2><div class="people-grid">{encountered or '<p>No encountered characters could be safely identified.</p>'}</div></section>
      <section class="panel" id="discussed"><h2>Discussed and mission-relevant</h2><dl class="reference-list">{discussed or '<div><dt>None</dt><dd>No discussed characters were safely identified.</dd></div>'}</dl></section>
      <section class="panel" id="politics"><h2>Known political picture</h2><div class="table-wrap"><table class="data-table"><thead><tr><th>Side or interest</th><th>Figures</th><th>What Henry knows</th></tr></thead><tbody>{politics}</tbody></table></div></section>
      <div class="notice red"><span class="notice-icon">!</span><div><strong>Deliberate omission</strong><p>Dormant names and future-facing profiles are excluded when they lack evidence of being encountered or discussed.</p></div></div>'''
    return document("people", "People & powers", "02", "Friends, officers, patrons and political figures already known in this save.", data, body, links)


def render_henry(data: dict[str, Any]) -> str:
    henry = data["henry"]
    choices = "".join(
        f'<article class="choice-entry"><span class="choice-glyph">◆</span><div><h2>{h(choice.get("title", ""))}</h2><p>{h(choice.get("summary", ""))}</p></div><span class="outcome">{h(choice.get("outcome", "Confirmed"))}</span></article>'
        for choice in henry["choices"]
    )
    traits = "".join(f"<li><strong>{h(trait)}</strong></li>" for trait in henry["traits"])
    save = data["save"]
    body = f'''<div class="wiki-layout"><div class="article-stack">
      <article class="panel" id="profile"><h2>Profile</h2>{paragraphs(henry["profile"], "standfirst")}</article>
      <section id="choices"><h2 style="font-size:1.35rem;margin:.5rem 0 .6rem">Recorded choices</h2><div class="choice-list">{choices or '<p>No save-specific choices were safely identified.</p>'}</div></section>
      <article class="panel" id="traits"><h2>Supported traits</h2><ul>{traits}</ul><p>These are narrative readings of confirmed choices, not hidden game statistics.</p></article>
    </div><aside class="infobox"><div class="infobox-title"><strong>Henry</strong><span>Current playthrough profile</span></div><div class="infobox-art"><span class="sigil">H</span></div><dl class="facts"><div><dt>Background</dt><dd>{h(save["background"])}</dd></div><div><dt>Last result</dt><dd>{h(save["last_result"])}</dd></div><div><dt>Current quest</dt><dd>{h(save["quest"])}</dd></div><div><dt>Position</dt><dd>{h(save["position"])}</dd></div></dl><p class="infobox-note">Only choices mapped to saved used sequences appear here.</p></aside></div>'''
    return document("henry", "Your Henry", "03", "The build, dialogue posture and confirmed outcomes that distinguish this playthrough.", data, body, [("profile", "Profile"), ("choices", "Recorded choices"), ("traits", "Supported traits")])


def render_checkpoint(data: dict[str, Any]) -> str:
    save = data["save"]
    resume = data["resume"]
    known = "".join(
        f'<div><dt>{h(item.get("label", ""))}</dt><dd>{h(item.get("value", ""))}</dd></div>'
        for item in resume["known_state"]
    )
    body = f'''{quest_strip(data)}<div class="wiki-layout" style="margin-top:1rem"><div class="article-stack">
      <article class="panel" id="resume"><h2>Resume briefing</h2><h3>What you were doing</h3><p>{h(resume["what_doing"])}</p><h3>What just happened</h3><p>{h(resume["just_happened"])}</p><h3>What to do now</h3><p>{h(resume["next_action"])}</p></article>
      <section class="panel" id="known-state"><h2>Known world state</h2><dl class="reference-list">{known}</dl></section>
      <div class="notice red" id="boundary"><span class="notice-icon">!</span><div><strong>Spoiler boundary: {h(save["position"])}</strong><p>{h(data["spoiler_boundary"])}</p></div></div>
      <div class="notice"><span class="notice-icon">✓</span><div><strong>Confidence</strong><p>{h(data["confidence"])}</p></div></div>
    </div><aside class="infobox"><div class="infobox-title"><strong>{h(save["quest"])}</strong><span>Current quest</span></div><div class="infobox-art"><span class="sigil">◆</span></div><dl class="facts"><div><dt>Region</dt><dd>{h(save["region"])}</dd></div><div><dt>State</dt><dd>{h(save["position"])}</dd></div><div><dt>Next</dt><dd>{h(save["objective"])}</dd></div><div><dt>Save type</dt><dd>{h(save["save_type"])}</dd></div><div><dt>Build</dt><dd>{h(save["build"])}</dd></div></dl><p class="infobox-note">{h(save["source_note"])}</p></aside></div>'''
    return document("checkpoint", "Current checkpoint", "04", "A returning-player briefing for the exact point where this save resumes.", data, body, [("resume", "Resume briefing"), ("known-state", "Known world state"), ("boundary", "Spoiler boundary")])


def validate_site(output: Path) -> int:
    checked = 0
    link_re = re.compile(r'(?:href|src)="([^"]+)"')
    id_re = re.compile(r'\bid="([^"]+)"')
    for page_name in PAGES:
        page = output / page_name
        text = page.read_text(encoding="utf-8")
        ids = id_re.findall(text)
        if len(ids) != len(set(ids)):
            raise CompendiumError(f"duplicate id in {page_name}")
        for url in link_re.findall(text):
            if url.startswith(("http://", "https://", "data:")):
                continue
            file_part, _, fragment = url.partition("#")
            target = output / (file_part or page_name)
            if not target.exists():
                raise CompendiumError(f"{page_name}: missing local target {url}")
            if fragment:
                target_text = target.read_text(encoding="utf-8")
                if f'id="{fragment}"' not in target_text:
                    raise CompendiumError(f"{page_name}: missing anchor {url}")
            checked += 1
    return checked


def prepare_output(output: Path, force: bool) -> None:
    known = set(PAGES) | {"assets/styles.css", "assets/site.js", "assets/kcd2-logo.png"}
    if output.exists() and not output.is_dir():
        raise CompendiumError(f"output is not a directory: {output}")
    if output.is_dir() and not force:
        existing = [name for name in known if (output / name).exists()]
        if existing:
            raise CompendiumError("generated compendium files already exist; choose a new directory or pass --force")
    (output / "assets").mkdir(parents=True, exist_ok=True)


def build(args: argparse.Namespace) -> dict[str, Any]:
    content_path = Path(args.content).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    if not content_path.is_file():
        raise CompendiumError(f"content JSON not found: {content_path}")
    try:
        data = json.loads(content_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CompendiumError(f"invalid content JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise CompendiumError("content JSON root must be an object")
    validate_content(data)
    prepare_output(output, args.force)

    asset_source = Path(__file__).resolve().parent.parent / "assets" / "compendium"
    for name in ("styles.css", "site.js"):
        source = asset_source / name
        if not source.is_file():
            raise CompendiumError(f"bundled asset missing: {source}")
        shutil.copyfile(source, output / "assets" / name)
    logo = Path(args.logo).expanduser().resolve() if args.logo else asset_source / "kcd2-logo.png"
    if not logo.is_file():
        raise CompendiumError(f"logo not found: {logo}")
    shutil.copyfile(logo, output / "assets" / "kcd2-logo.png")

    rendered = {
        "index.html": render_index(data),
        "chronicle.html": render_chronicle(data),
        "people.html": render_people(data),
        "henry.html": render_henry(data),
        "checkpoint.html": render_checkpoint(data),
    }
    for name, text in rendered.items():
        (output / name).write_text(text + "\n", encoding="utf-8")
    links = validate_site(output)
    return {"output": str(output), "pages": list(PAGES), "validated_local_links": links}


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Build a spoiler-safe multi-page KCD2 save compendium.")
    result.add_argument("--content", required=True, help="Vetted compendium content JSON")
    result.add_argument("--output", required=True, help="Dedicated output directory")
    result.add_argument("--logo", help="Optional replacement PNG logo")
    result.add_argument("--force", action="store_true", help="Overwrite known generated files")
    return result


def main() -> int:
    try:
        result = build(parser().parse_args())
    except (OSError, CompendiumError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
