#!/usr/bin/env python3
"""Validate the static ASCII Cube site before it is published.

Checks HTML structure, inline JavaScript syntax, import maps, local asset
references, Dockerfile COPY sources, and a basic docker-compose.yml shape.
Uses only the Python standard library plus the node binary on PATH.
"""

from __future__ import annotations

import json
import re
import shlex
import subprocess
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parent.parent

VOID_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}

JS_TYPES = {"", "module", "text/javascript", "application/javascript"}
GET_ELEMENT_BY_ID = re.compile(r"""getElementById\(\s*(['"])([^'"]+)\1\s*\)""")


class PageParser(HTMLParser):
    """Collect structure, ids, scripts, and local references from one HTML file."""

    def __init__(self, filename: str) -> None:
        super().__init__(convert_charrefs=True)
        self.filename = filename
        self.errors: list[str] = []
        self.stack: list[tuple[str, int]] = []
        self.ids: dict[str, str] = {}
        self.scripts: list[dict[str, str]] = []
        self.refs: list[tuple[str, str, int]] = []
        self.has_doctype = False
        self.saw_html = False
        self.saw_head = False
        self.saw_body = False
        self.title_parts: list[str] = []
        self._in_title = False
        self._script: dict[str, str] | None = None

    def _error(self, message: str) -> None:
        line, column = self.getpos()
        self.errors.append(f"{self.filename}:{line}:{column}: {message}")

    def handle_decl(self, decl: str) -> None:
        if decl.lower() == "doctype html":
            self.has_doctype = True

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._open(tag, attrs, self_closing=False)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._open(tag, attrs, self_closing=True)

    def _open(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
        self_closing: bool,
    ) -> None:
        attr_map: dict[str, str | None] = {}
        for key, value in attrs:
            if key in attr_map:
                self._error(f"duplicate attribute {key!r} on <{tag}>")
            attr_map[key] = value

        element_id = attr_map.get("id")
        if element_id is not None:
            if element_id == "":
                self._error(f"empty id on <{tag}>")
            elif element_id in self.ids:
                self._error(
                    f"duplicate id {element_id!r} on <{tag}> "
                    f"(already used on <{self.ids[element_id]}>)"
                )
            else:
                self.ids[element_id] = tag

        for attr in ("href", "src"):
            value = attr_map.get(attr)
            if value:
                line, _column = self.getpos()
                self.refs.append((attr, value, line))

        if tag == "html":
            self.saw_html = True
            if not self.has_doctype:
                self._error("DOCTYPE html is missing before <html>")
        elif tag == "head":
            self.saw_head = True
        elif tag == "body":
            self.saw_body = True
        elif tag == "title":
            self._in_title = True
        elif tag == "script" and "src" not in attr_map:
            self._script = {
                "type": (attr_map.get("type") or "").strip().lower(),
                "data": "",
            }

        if self_closing or tag in VOID_TAGS:
            return
        line, _column = self.getpos()
        self.stack.append((tag, line))

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        if tag == "script" and self._script is not None:
            self.scripts.append(self._script)
            self._script = None

        if tag in VOID_TAGS:
            return
        if not self.stack:
            self._error(f"unexpected closing tag </{tag}>")
            return
        open_tag, open_line = self.stack.pop()
        if open_tag != tag:
            self._error(
                f"mismatched </{tag}>; expected </{open_tag}> "
                f"opened on line {open_line}"
            )

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_parts.append(data)
        if self._script is not None:
            self._script["data"] += data

    def finish(self) -> None:
        self.close()
        for tag, line in self.stack:
            self.errors.append(f"{self.filename}:{line}: unclosed <{tag}>")
        if not self.has_doctype:
            self.errors.append(f"{self.filename}: missing <!DOCTYPE html>")
        if not self.saw_html:
            self.errors.append(f"{self.filename}: missing <html>")
        if not self.saw_head:
            self.errors.append(f"{self.filename}: missing <head>")
        if not self.saw_body:
            self.errors.append(f"{self.filename}: missing <body>")
        title = "".join(self.title_parts).strip()
        if not title:
            self.errors.append(f"{self.filename}: missing or empty <title>")


def is_external(url: str) -> bool:
    value = url.strip()
    if not value or value.startswith("#"):
        return True
    lowered = value.lower()
    return lowered.startswith(
        ("http://", "https://", "//", "data:", "mailto:", "tel:", "javascript:")
    )


def local_reference(url: str) -> str:
    path = url.split("#", 1)[0].split("?", 1)[0]
    return unquote(path.strip())


def check_html_file(path: Path, errors: list[str]) -> PageParser:
    parser = PageParser(path.name)
    parser.feed(path.read_text(encoding="utf-8"))
    parser.finish()
    errors.extend(parser.errors)

    for attr, url, line in parser.refs:
        if is_external(url):
            continue
        relative = local_reference(url)
        if not relative:
            continue
        target = (path.parent / relative).resolve()
        if ROOT.resolve() not in target.parents and target != ROOT.resolve():
            errors.append(f"{path.name}:{line}: {attr} escapes the repository: {url}")
            continue
        if not target.is_file():
            errors.append(f"{path.name}:{line}: missing {attr} target {relative}")

    return parser


def check_javascript(source: str, label: str, errors: list[str]) -> None:
    with tempfile.NamedTemporaryFile(
        "w",
        suffix=".mjs",
        delete=False,
        encoding="utf-8",
    ) as handle:
        handle.write(source)
        temporary = Path(handle.name)
    try:
        result = subprocess.run(
            ["node", "--check", str(temporary)],
            capture_output=True,
            text=True,
            check=False,
        )
    finally:
        temporary.unlink(missing_ok=True)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        detail = detail.replace(str(temporary), label)
        errors.append(f"{label}: JavaScript syntax check failed\n{detail}")


def check_scripts(page: PageParser, errors: list[str]) -> None:
    module_count = 0
    importmap_count = 0
    for index, script in enumerate(page.scripts, start=1):
        kind = script["type"]
        label = f"{page.filename} script #{index}"
        source = script["data"]
        if kind == "importmap":
            importmap_count += 1
            try:
                data = json.loads(source)
            except json.JSONDecodeError as exc:
                errors.append(f"{label}: import map is not valid JSON ({exc})")
                continue
            imports = data.get("imports") if isinstance(data, dict) else None
            if not isinstance(imports, dict) or not imports:
                errors.append(f"{label}: import map needs a non-empty imports object")
                continue
            for specifier, target in imports.items():
                if not isinstance(target, str) or not target.startswith("https://"):
                    errors.append(
                        f"{label}: import {specifier!r} must point at an https URL"
                    )
        elif kind in JS_TYPES:
            if kind == "module":
                module_count += 1
            if not source.strip():
                errors.append(f"{label}: inline script is empty")
                continue
            check_javascript(source, label, errors)
        else:
            errors.append(f"{label}: unsupported script type {kind!r}")

    if page.filename == "index.html":
        if module_count != 1:
            errors.append(
                f"index.html: expected 1 inline module script, found {module_count}"
            )
        if importmap_count != 1:
            errors.append(
                f"index.html: expected 1 import map, found {importmap_count}"
            )
        module_sources = [
            script["data"] for script in page.scripts if script["type"] == "module"
        ]
        html_ids = set(page.ids)
        for source in module_sources:
            for match in GET_ELEMENT_BY_ID.finditer(source):
                element_id = match.group(2)
                if element_id not in html_ids:
                    errors.append(
                        f"index.html: getElementById({element_id!r}) "
                        "has no matching element"
                    )


def check_dockerfile(errors: list[str]) -> None:
    path = ROOT / "Dockerfile"
    if not path.is_file():
        errors.append("Dockerfile is missing")
        return
    text = path.read_text(encoding="utf-8")
    if not re.search(r"(?mi)^FROM\s+\S+", text):
        errors.append("Dockerfile: missing FROM instruction")

    copied: list[str] = []
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped.upper().startswith("COPY ") or stripped.upper().startswith(
            "COPY --"
        ):
            continue
        parts = shlex.split(stripped)
        if len(parts) < 3:
            errors.append(f"Dockerfile: COPY needs a source and a destination: {stripped}")
            continue
        for source in parts[1:-1]:
            copied.append(source)
            target = ROOT / source
            if not target.exists():
                errors.append(f"Dockerfile: COPY source does not exist: {source}")

    for html_name in ("index.html", "about.html"):
        if html_name not in copied:
            errors.append(f"Dockerfile: {html_name} is not copied into the image")


def check_compose(errors: list[str]) -> None:
    path = ROOT / "docker-compose.yml"
    if not path.is_file():
        errors.append("docker-compose.yml is missing")
        return
    text = path.read_text(encoding="utf-8")
    if "\t" in text:
        errors.append("docker-compose.yml: use spaces for indentation, not tabs")

    quote_balance = {"'": 0, '"': 0}
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        if line[:indent] != " " * indent:
            errors.append(f"docker-compose.yml:{number}: mixed indentation")
        if indent % 2 != 0:
            errors.append(
                f"docker-compose.yml:{number}: indent is not a multiple of 2 spaces"
            )
        for quote in quote_balance:
            quote_balance[quote] += stripped.count(quote)
        if stripped.startswith("- "):
            continue
        if ":" not in stripped:
            errors.append(f"docker-compose.yml:{number}: expected a key: value entry")

    for quote, count in quote_balance.items():
        if count % 2 != 0:
            errors.append(f"docker-compose.yml: unbalanced {quote} quotes")

    if not re.search(r"(?m)^services:\s*$", text):
        errors.append("docker-compose.yml: missing top-level services key")
    if not re.search(r"(?m)^\s+build:\s+\.\s*$", text):
        errors.append("docker-compose.yml: expected a service with build: .")
    if not (ROOT / "Dockerfile").is_file():
        errors.append("docker-compose.yml: build context is missing a Dockerfile")


def main() -> int:
    errors: list[str] = []
    html_files = sorted(ROOT.glob("*.html"))
    if not html_files:
        errors.append("no HTML files found in the repository root")

    pages: list[PageParser] = []
    for path in html_files:
        pages.append(check_html_file(path, errors))

    for page in pages:
        check_scripts(page, errors)

    check_dockerfile(errors)
    check_compose(errors)

    if errors:
        print("Static site validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    html_names = ", ".join(path.name for path in html_files)
    print(f"HTML structure ok: {html_names}")
    script_count = sum(len(page.scripts) for page in pages)
    print(f"Inline scripts ok: {script_count} checked with node --check or JSON")
    ref_count = sum(
        1
        for _path, page in zip(html_files, pages)
        for _attr, url, _line in page.refs
        if not is_external(url) and local_reference(url)
    )
    print(f"Local asset references ok: {ref_count}")
    print("Dockerfile COPY sources ok")
    print("docker-compose.yml structure ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
