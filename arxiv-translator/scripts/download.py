#!/usr/bin/env python3
"""
Download arXiv e-print, extract, pick main .tex, fetch paper title (PDF basename).
Usage:
  python download.py <paper_id> <work_dir>
  python download.py --library-dir <library_dir> <paper_id>
  python download.py --library-dir <library_dir> --local-work-copy <paper_id>

stdout: shell assignments including WORK_DIR, MAIN_TEX, PDF_NAME, and
library-mode PAPER_DIR/PDF_PATH.
"""
import gzip
import html
import os
import re
import shutil
import sys
import tarfile
import tempfile
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET


DOWNLOAD_ENV = "download.env"
LOCAL_WORK_MARKER = ".arxiv-translator-local-work"
_INVALID_FILENAME_CHARS_RE = re.compile(r'[<>:"|?*]')
_TITLE_PREFIX_COLON_RE = re.compile(r"^([A-Za-z][A-Za-z0-9]{1,39}):\s*")
_EMOJI_RE = re.compile(
    "["
    "\U0001F1E6-\U0001F1FF"
    "\U0001F300-\U0001FAFF"
    "\u2600-\u27BF"
    "\u200d"
    "\ufe0f"
    "]"
)


def extract_tar_archive(tf, work_dir):
    """Use the safer tar extraction mode when the runtime supports it."""
    if sys.version_info >= (3, 12):
        tf.extractall(work_dir, filter="data")
    else:
        tf.extractall(work_dir)


def download_and_extract(paper_id, work_dir):
    os.makedirs(work_dir, exist_ok=True)
    source_path = os.path.join(work_dir, "source.bin")

    url = f"https://arxiv.org/e-print/{paper_id}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            with open(source_path, "wb") as f:
                shutil.copyfileobj(resp, f)
    except Exception as e:
        print(f"Error: download failed {url}\n{e}", file=sys.stderr)
        sys.exit(1)

    extracted = False
    try:
        if tarfile.is_tarfile(source_path):
            with tarfile.open(source_path) as tf:
                extract_tar_archive(tf, work_dir)
            extracted = True
    except Exception:
        pass
    if not extracted:
        try:
            with gzip.open(source_path, "rb") as gz, open(os.path.join(work_dir, "paper.tex"), "wb") as out:
                shutil.copyfileobj(gz, out)
            extracted = True
        except Exception:
            pass
    if not extracted:
        shutil.copy(source_path, os.path.join(work_dir, "paper.tex"))
    os.remove(source_path)

    tex_files = []
    for root, _, files in os.walk(work_dir):
        for f in files:
            if f.endswith(".tex"):
                tex_files.append(os.path.relpath(os.path.join(root, f), work_dir))
    if not tex_files:
        print("Error: no .tex files found; this paper may be PDF-only.", file=sys.stderr)
        sys.exit(1)
    return tex_files


_RE_DOCCLASS = re.compile(r"\\documentclass")
_RE_INPUT = re.compile(r"\\(?:input|include)\s*\{([^}]+)\}")
_ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}
_RE_CITATION_TITLE = re.compile(
    r'<meta\s+name=["\']citation_title["\']\s+content=["\'](.*?)["\']',
    re.IGNORECASE,
)
_RE_HTML_TITLE = re.compile(r"<title>\s*(?:\[[^\]]+\]\s*)?(.*?)\s*</title>", re.IGNORECASE | re.DOTALL)


def find_main_tex(work_dir, tex_files):
    candidates = []
    for tf in tex_files:
        try:
            content = open(os.path.join(work_dir, tf), "r", encoding="utf-8", errors="replace").read()
        except Exception:
            continue
        if _RE_DOCCLASS.search(content):
            candidates.append((tf, content))
    if not candidates:
        print("Error: no .tex file containing \\documentclass found.", file=sys.stderr)
        sys.exit(1)
    if len(candidates) == 1:
        return candidates[0]
    return max(candidates, key=lambda c: len(_RE_INPUT.findall(c[1])))


def fetch_arxiv_title(paper_id):
    """Prefer arXiv API for title; fall back to abstract page metadata."""
    title = fetch_arxiv_title_from_api(paper_id)
    if title:
        return title
    return fetch_arxiv_title_from_abs_page(paper_id)


def fetch_arxiv_title_from_api(paper_id):
    query = urllib.parse.urlencode({"id_list": paper_id})
    url = f"https://arxiv.org/api/query?{query}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "arxiv-translator/1.0 (+https://arxiv.org/help/api/user-manual)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read()
    except Exception:
        return None
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return None
    entry = root.find("atom:entry", _ATOM_NS)
    if entry is None:
        return None
    title_el = entry.find("atom:title", _ATOM_NS)
    if title_el is None:
        return None
    title = " ".join(title_el.itertext()).strip()
    return re.sub(r"\s+", " ", title) or None


def fetch_arxiv_title_from_abs_page(paper_id):
    url = f"https://arxiv.org/abs/{paper_id}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            page = resp.read().decode("utf-8", errors="replace")
    except Exception:
        return None
    for pattern in (_RE_CITATION_TITLE, _RE_HTML_TITLE):
        match = pattern.search(page)
        if not match:
            continue
        title = html.unescape(match.group(1)).strip()
        title = re.sub(r"\s+", " ", title)
        if title:
            return title
    return None


def pdf_name_from_title(title, fallback, max_len=240):
    """Use paper title as PDF basename: keep text, strip path-illegal characters only."""
    if not title or not str(title).strip():
        return fallback
    s = " ".join(str(title).split())
    s = s.replace("\x00", "")
    s = s.replace("/", "-").replace("\\", "-")
    s = _TITLE_PREFIX_COLON_RE.sub(_format_title_prefix, s)
    s = _INVALID_FILENAME_CHARS_RE.sub("_", s)
    s = _EMOJI_RE.sub("", s)
    s = " ".join(s.split())
    s = s.strip().rstrip(".")
    if not s:
        return fallback
    if max_len and len(s) > max_len:
        s = s[:max_len].rstrip()
    return s


def _format_title_prefix(match):
    prefix = match.group(1)
    if prefix.isupper() or any(ch.isupper() for ch in prefix[1:]) or any(ch.isdigit() for ch in prefix):
        return f"【{prefix}】"
    return match.group(0)


def paper_dir_name(paper_id, pdf_name):
    title = pdf_name_from_title(pdf_name, "paper", max_len=220)
    return f"{paper_id} - {title}"


def resolve_paper_dir(library_dir, paper_id, pdf_name):
    """Return the single-paper directory, reusing an existing arXiv-id prefix."""
    library_dir = os.path.abspath(os.path.expanduser(library_dir or "."))
    os.makedirs(library_dir, exist_ok=True)
    prefix = f"{paper_id} - "
    try:
        entries = sorted(os.listdir(library_dir))
    except OSError:
        entries = []
    for entry in entries:
        path = os.path.join(library_dir, entry)
        if os.path.isdir(path) and (entry == paper_id or entry.startswith(prefix)):
            return path
    return os.path.join(library_dir, paper_dir_name(paper_id, pdf_name))


def _path_for_env(path, paper_dir):
    path = os.path.abspath(path)
    paper_dir = os.path.abspath(paper_dir)
    rel = os.path.relpath(path, paper_dir)
    if rel == ".":
        return "."
    if rel.startswith("..") or os.path.isabs(rel):
        return path
    if os.name == "nt":
        rel = rel.replace("\\", "/")
    return rel


def write_download_env(paper_dir, paper_id, work_dir, main_tex, pdf_name, local_work_dir=None):
    """Persist per-paper metadata so later commands can target only this folder."""
    os.makedirs(paper_dir, exist_ok=True)
    pdf_path = os.path.join(paper_dir, os.path.basename(os.path.abspath(paper_dir)) + ".pdf")
    env_path = os.path.join(paper_dir, DOWNLOAD_ENV)
    lines = [
        _sh_var_assign("PAPER_ID", paper_id),
        _sh_var_assign("WORK_DIR", _path_for_env(work_dir, paper_dir)),
        _sh_var_assign("MAIN_TEX", main_tex),
        _sh_var_assign("PDF_NAME", pdf_name),
        _sh_var_assign("PDF_PATH", _path_for_env(pdf_path, paper_dir)),
    ]
    if local_work_dir:
        lines.append(_sh_var_assign("LOCAL_WORK_DIR", os.path.abspath(local_work_dir)))
    with open(env_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return env_path


def _sh_var_assign(name, value):
    esc = str(value).replace("'", "'\\''")
    return f"{name}='{esc}'"


def _print_download_vars(work_dir, main_tex, pdf_name, paper_dir=None, pdf_path=None):
    print(_sh_var_assign("WORK_DIR", os.path.abspath(work_dir)))
    print(_sh_var_assign("MAIN_TEX", main_tex))
    print(_sh_var_assign("PDF_NAME", pdf_name))
    if paper_dir:
        print(_sh_var_assign("PAPER_DIR", os.path.abspath(paper_dir)))
    if pdf_path:
        print(_sh_var_assign("PDF_PATH", os.path.abspath(pdf_path)))


def _download_to_work_dir(paper_id, work_dir):
    tex_files = download_and_extract(paper_id, work_dir)
    rel_path, _ = find_main_tex(work_dir, tex_files)
    rel_path = rel_path.replace("\\", "/")
    fallback = os.path.splitext(os.path.basename(rel_path))[0]
    pdf_name = pdf_name_from_title(fetch_arxiv_title(paper_id), fallback)
    return rel_path, pdf_name


def create_local_work_dir(paper_id):
    safe_id = re.sub(r"[^A-Za-z0-9._-]", "_", paper_id)
    work_dir = tempfile.mkdtemp(prefix=f"arxiv-translator-{safe_id}-")
    with open(os.path.join(work_dir, LOCAL_WORK_MARKER), "w", encoding="utf-8") as f:
        f.write(f"PAPER_ID={paper_id}\n")
    return work_dir


def _download_to_library(paper_id, library_dir, local_work_copy=False):
    pdf_name = pdf_name_from_title(fetch_arxiv_title(paper_id), paper_id)
    paper_dir = resolve_paper_dir(library_dir, paper_id, pdf_name)
    work_dir = (
        create_local_work_dir(paper_id)
        if local_work_copy
        else os.path.join(paper_dir, ".tmp_arxiv", paper_id)
    )
    try:
        main_tex, pdf_name = _download_to_work_dir(paper_id, work_dir)
    except SystemExit:
        if local_work_copy:
            shutil.rmtree(work_dir, ignore_errors=True)
        raise
    env_path = write_download_env(
        paper_dir,
        paper_id,
        work_dir,
        main_tex,
        pdf_name,
        local_work_dir=work_dir if local_work_copy else None,
    )
    pdf_path = os.path.join(paper_dir, os.path.basename(os.path.abspath(paper_dir)) + ".pdf")
    return paper_dir, work_dir, main_tex, pdf_name, pdf_path, env_path


def main(argv):
    if len(argv) == 2:
        paper_id, work_dir = argv
        main_tex, pdf_name = _download_to_work_dir(paper_id, work_dir)
        _print_download_vars(work_dir, main_tex, pdf_name)
        return 0

    if len(argv) == 3 and argv[0] == "--library-dir":
        library_dir, paper_id = argv[1], argv[2]
        paper_dir, work_dir, main_tex, pdf_name, pdf_path, _ = _download_to_library(paper_id, library_dir)
        _print_download_vars(work_dir, main_tex, pdf_name, paper_dir, pdf_path)
        return 0

    if len(argv) == 4 and argv[0] == "--library-dir" and argv[2] == "--local-work-copy":
        library_dir, paper_id = argv[1], argv[3]
        paper_dir, work_dir, main_tex, pdf_name, pdf_path, _ = _download_to_library(
            paper_id, library_dir, local_work_copy=True
        )
        _print_download_vars(work_dir, main_tex, pdf_name, paper_dir, pdf_path)
        return 0

    print(
        "Usage: python download.py <paper_id> <work_dir>\n"
        "   or: python download.py --library-dir <library_dir> <paper_id>\n"
        "   or: python download.py --library-dir <library_dir> --local-work-copy <paper_id>",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
