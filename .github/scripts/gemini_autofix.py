"""
Gemini Autofix Script
Reads the existing Gemini Code Review comment on a PR (marker <!-- gemini-code-review-bot -->),
pulls the 🔴 Crítico / 🟡 Advertencia issues out of it, and asks Gemini for the corrected full
content of each affected file in a single API call — no agentic tool-calling loop.
Requiere: pip install google-genai requests
"""

import os
import re
import sys

import requests

from google import genai as _genai
from google.genai import types as _gtypes

import gemini_review as gr

FILE_RE = re.compile(r'<file path="([^"]+)">\s*(.*?)\s*</file>', re.DOTALL)
CHANGELOG_RE = re.compile(r"<changelog>\s*(.*?)\s*</changelog>", re.DOTALL)
SKIPPED_RE = re.compile(r"<skipped>\s*(.*?)\s*</skipped>", re.DOTALL)

AUTOFIX_SYSTEM_PROMPT = """You will be given an existing PR code review (written in Spanish) and the
full current content of each file it flagged. Fix ONLY the issues marked 🔴 Crítico or 🟡
Advertencia. Do NOT touch anything marked 🔵 Sugerencia or ⚪ Opinión — leave those exactly as they
are, and do not invent fixes for issues the review didn't raise.

For each file that needs a change, output its FULL corrected content:

<file path="exact/path/as/given.ts">
// full corrected file content
</file>

If a given file needs no changes after all (its only issues were 🔵/⚪, or you determine it's
already correct), do not include a <file> block for it.

After the <file> blocks, write a changelog in Spanish, one line per fix applied, in this exact
format:

<changelog>
| # | Archivo | Línea | Issue corregido |
|---|---------|-------|-----------------|
| 1 | ruta/al/archivo.ts | 42 | Descripción breve del fix |
</changelog>

And a short list (Spanish) of the 🔵/⚪ issues you deliberately left untouched, if any:

<skipped>
- Descripción de la sugerencia opcional no aplicada
</skipped>

If there is nothing to fix (no 🔴/🟡 issues in the review, or every flagged file already looks
correct), output only:

<nothing_to_fix/>
"""


def fetch_sticky_review_comment(repo: str, pr_number: int, token: str) -> str | None:
    url = f"{gr.GITHUB_API}/repos/{repo}/issues/{pr_number}/comments"
    resp = requests.get(url, headers=gr.github_headers(token), timeout=30)
    resp.raise_for_status()
    for comment in resp.json():
        if gr.STICKY_MARKER in comment.get("body", ""):
            return comment["body"]
    return None


def extract_flagged_files(review_body: str) -> set:
    files = set()
    for line in review_body.splitlines():
        if "🔴" in line or "🟡" in line:
            for cell in line.split("|"):
                m = re.search(r"`([^`]+\.\w+)`", cell.strip())
                if m:
                    files.add(m.group(1))
    return files


def read_file_safe(path: str) -> str | None:
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError as exc:
        print(f"[WARN] No se pudo leer {path}: {exc}", file=sys.stderr)
        return None


def build_prompt(review_body: str, file_contents: dict) -> str:
    parts = [AUTOFIX_SYSTEM_PROMPT, "\n---\n## Review to apply\n\n", review_body, "\n\n---\n## Current file contents\n"]
    for path, content in file_contents.items():
        parts.append(f'\n<file path="{path}">\n{content}\n</file>\n')
    return "".join(parts)


def call_gemini(prompt: str, api_key: str, model_name: str):
    client = _genai.Client(api_key=api_key)
    return client.models.generate_content(
        model=f"models/{model_name}",
        contents=prompt,
        config=_gtypes.GenerateContentConfig(temperature=0.1, max_output_tokens=8192),
    )


def save_corrected_files(raw: str) -> list:
    saved = []
    for file_path, content in FILE_RE.findall(raw):
        dir_name = os.path.dirname(file_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as fh:
            fh.write(content)
        saved.append(file_path)
        print(f"[INFO] Corregido: {file_path}", file=sys.stderr)
    return saved


def write_pr_body(pr_number: int, head_ref: str, raw: str) -> None:
    changelog_match = CHANGELOG_RE.search(raw)
    skipped_match = SKIPPED_RE.search(raw)
    changelog = changelog_match.group(1).strip() if changelog_match else "| 1 | - | - | (sin detalle) |"
    skipped = skipped_match.group(1).strip() if skipped_match else "- Ninguno."

    body = f"""🤖 **Gemini Autofix — corrections for PR #{pr_number}**

Este PR aplica automáticamente los issues 🔴 y 🟡 detectados en el review.

## Correcciones aplicadas

{changelog}

## Issues opcionales no aplicados (🔵)
{skipped}

> Revisá los cambios antes de hacer merge hacia `{head_ref}`.
"""
    with open("autofix-pr-body.md", "w", encoding="utf-8") as fh:
        fh.write(body)


def main() -> None:
    gemini_key = gr.get_env("GEMINI_API_KEY")
    gh_token = gr.get_env("GITHUB_TOKEN")
    repository = gr.get_env("GITHUB_REPOSITORY")
    pr_num = int(gr.get_env("PR_NUMBER"))
    head_ref = os.environ.get("PR_HEAD_REF", "").strip()
    model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip()

    review_body = fetch_sticky_review_comment(repository, pr_num, gh_token)
    if review_body is None:
        print("[WARN] No se encontró un comentario de review previo (marker no encontrado).", file=sys.stderr)
        gr.write_github_output("has_fixes", "false")
        return

    flagged_files = extract_flagged_files(review_body)
    if not flagged_files:
        print("[INFO] El review no tiene issues 🔴/🟡 con archivo identificable.", file=sys.stderr)
        gr.write_github_output("has_fixes", "false")
        return

    file_contents = {}
    for path in flagged_files:
        content = read_file_safe(path)
        if content is not None:
            file_contents[path] = content

    if not file_contents:
        print("[WARN] Ninguno de los archivos marcados se pudo leer del checkout local.", file=sys.stderr)
        gr.write_github_output("has_fixes", "false")
        return

    prompt = build_prompt(review_body, file_contents)

    print(f"[INFO] Pidiendo fixes a {model_name} para {len(file_contents)} archivo(s)...", file=sys.stderr)
    try:
        response = call_gemini(prompt, gemini_key, model_name)
    except Exception as exc:
        print(f"[ERROR] Fallo en la API de Gemini: {exc}", file=sys.stderr)
        sys.exit(1)

    raw = response.text

    real_model = gr.get_real_model(response, model_name)
    in_tok, out_tok, cached_tok = gr.get_token_counts(response)
    cost = gr.calculate_cost(real_model, in_tok, out_tok, cached_tok)
    print(
        f"[INFO] Tokens — input: {in_tok} (cache: {cached_tok}), output: {out_tok} | "
        f"Costo real: ${cost:.6f} USD ({real_model})",
        file=sys.stderr,
    )
    try:
        gr.post_cost_comment(repository, pr_num, gh_token, model_name, real_model, in_tok, out_tok, cached_tok, cost)
    except Exception as exc:
        print(f"[WARN] No se pudo postear el comentario de costo: {exc}", file=sys.stderr)

    if "<nothing_to_fix" in raw:
        print("[INFO] Gemini determinó que no hay nada para corregir.", file=sys.stderr)
        gr.write_github_output("has_fixes", "false")
        return

    saved = save_corrected_files(raw)
    if not saved:
        print("[WARN] La respuesta no trajo bloques <file>. No se aplicó nada.", file=sys.stderr)
        gr.write_github_output("has_fixes", "false")
        return

    write_pr_body(pr_num, head_ref, raw)
    gr.write_github_output("has_fixes", "true")
    print(f"[OK] {len(saved)} archivo(s) corregido(s).", file=sys.stderr)


if __name__ == "__main__":
    main()
