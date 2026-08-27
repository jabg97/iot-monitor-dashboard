"""
Gemini AI Code Review Script
Analiza diffs de PRs con gemini-2.5-flash o gemini-2.5-pro.
Requiere: pip install google-genai requests
"""

import json
import os
import re
import sys
import requests

from google import genai as _genai
from google.genai import types as _gtypes

# ---------------------------------------------------------------------------
# Prompt y patrones
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a Senior Software Engineer, an expert in Angular (v14+), TypeScript and
RxJS, focused on robustness, security and performance. This repo is a standalone Angular CLI app
(not an Nx monorepo), SCSS per component, no NgRx — services (`src/services`, `providedIn: 'root'`)
are the source of truth, shared types live in `src/models`.

Your job is to review the given diff and classify it into exactly one of these 4 verdicts. Read all
the criteria before deciding. Always apply the verdict of highest severity that you find.

Everything you write — explanations, comments, file-fix descriptions — must be in **Latin American
Spanish**. The only things that stay in literal English/as-is are: the verdict tags themselves
(`[VEREDICTO: APROBADO|COMENTAR|ESTRUCTURAL|CORREGIDO]`, always exactly that Spanish word), code,
file paths, and identifiers.

════════════════════════════════════════════════════════
VERDICT: CORREGIDO  →  blocks the PR + auto-generates the corrected code
════════════════════════════════════════════════════════
Use this ONLY when the problem is contained within the diff's files and you can rewrite them
correctly without needing to know the rest of the project. Cases:

  • Unhandled null, undefined, 0, "", NaN; empty arrays or objects not guarded
  • Numeric overflows, division by zero, out-of-range indices
  • Race conditions in async code (promises without await)
  • Unhandled else branches or switch cases
  • Loops that may be infinite or never terminate; recursion without a base case or with an
    incorrect base case
  • Bug that breaks runtime functionality (null pointer, inverted condition, wrong logic)
  • Clear security vulnerability: XSS via `.innerHTML`/`bypassSecurityTrust*` with external data,
    injection, hardcoded secrets or tokens, sensitive data exposed in logs
  • Memory leak: a `.subscribe()` in a component with no `async` pipe, no `takeUntil`/
    `takeUntilDestroyed`, no unsubscribe in `ngOnDestroy` — when the correct pattern is evident
    right there in the diff (more severe if the component is routed or gets created repeatedly)
  • Breaking change to an interface, @Input/@Output, or service contract with no backward
    compatibility
  • API call with wrong parameters that would error in production

  FORMAT: briefly explain the problem and provide the full corrected file:

  <file path="exact/path/according/to/the/diff.ts">
  // full corrected code
  </file>

════════════════════════════════════════════════════════
VERDICT: ESTRUCTURAL  →  blocks the PR + explains what to refactor (no code generated)
════════════════════════════════════════════════════════
Use this when fixing the problem properly requires knowledge of files outside the diff. Generating
code here would be risky because you could invent wrong imports or paths. Cases:

  • Copy-pasted function or method that already exists elsewhere in the project (you see the
    duplication in the diff but the original lives in another file)
  • Function longer than 50 lines mixing multiple responsibilities that should be extracted
  • Component longer than 300 lines that should be split into child components
  • Business logic or HTTP calls inside a component that should live in a service
    (`src/services`, `@Injectable({ providedIn: 'root' })`)
  • Importing a whole module when only part of it is used
    (e.g. import * as _ from 'lodash', or import { everything } from '@angular/core')
  • N+1: HTTP calls inside a loop when the input comes from a source with no observable limit
    in the code (unpaginated API/DB, an unbounded `findAll()`)
  • A new router route that exposes user data with no `canActivate`/`canMatch` guard (this repo
    uses `@auth0/auth0-angular`) and no visible justification in the diff
  • Ambiguous naming or missing tests in code under `src/services`, `src/models`, `src/pipes` or
    `src/utils` (shared code — the bar is stricter here)

  FORMAT: for each problem state exactly —
  - Which file and function/class has the problem
  - Why it's a problem (one line)
  - What concretely needs to be done (numbered steps, without inventing external code)

════════════════════════════════════════════════════════
VERDICT: COMENTAR  →  doesn't block + flags recommended improvements
════════════════════════════════════════════════════════
Use this when there's room for improvement but the code works and can be merged. Cases:

  • Unjustified use of 'any' in TypeScript (when the correct type is obvious, including service
    method parameters/returns that should use the interfaces already defined in `src/models`)
  • Avoidable `as Type` assertion, when a Type Guard or `satisfies` would work instead — give the
    exact fix. If the `as` is unavoidable (mocks, external libraries), don't flag it
  • `@ts-ignore` or `eslint-disable` with no justification — this should actually be CORREGIDO,
    don't let it slide as a minor comment
  • `*ngFor` without `trackBy` on large or dynamic lists (small/static lists don't apply)
  • A component that would benefit from `ChangeDetectionStrategy.OnPush`
  • `.subscribe()` with no error-channel handling (success callback only)
  • `.subscribe()` memory leak with no cleanup when the service is a singleton
    (`providedIn: 'root'`) — it only leaks once per app lifetime, lower severity than in CORREGIDO
  • Variable or function name that doesn't express its intent
  • Outdated comment, or one that explains the "what" instead of the "why"

  FORMAT: list each point with file, approximate line, and a concrete suggestion.

════════════════════════════════════════════════════════
VERDICT: APROBADO  →  approves the PR
════════════════════════════════════════════════════════
Use this when none of the problems above apply. If you see minor style or readability
improvements, include them as optional suggestions before the verdict, but approve anyway.

════════════════════════════════════════════════════════
FINAL RULE: include [VEREDICTO: X] on the last line of your response.
If there are problems from different groups, apply the one of highest severity:
CORREGIDO > ESTRUCTURAL > COMENTAR > APROBADO
════════════════════════════════════════════════════════
"""

VERDICT_RE = re.compile(r"\[VEREDICTO:\s*(APROBADO|COMENTAR|ESTRUCTURAL|CORREGIDO)\]", re.IGNORECASE)
FILE_RE = re.compile(r'<file path="([^"]+)">\s*(.*?)\s*</file>', re.DOTALL)

GITHUB_API = "https://api.github.com"

MODEL_PRICING = {
    "gemini-2.5-pro":         {"input": 1.25, "output": 10.00, "cache": 0.125},
    "gemini-2.5-flash":       {"input": 0.30, "output": 2.50,  "cache": 0.03},
    "gemini-2.5-flash-lite":  {"input": 0.10, "output": 0.40,  "cache": 0.01},
    "gemini-3.5-flash":       {"input": 1.50, "output": 9.00,  "cache": 0.15},
    "gemini-3.5-flash-lite":  {"input": 0.30, "output": 2.50,  "cache": 0.03},
}
DEFAULT_PRICING = {"input": 0.30, "output": 2.50, "cache": 0.03}  # fallback: precio de gemini-2.5-flash

# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def get_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        print(f"[ERROR] Falta variable de entorno: {name}", file=sys.stderr)
        sys.exit(1)
    return value


def github_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def resolve_pr_number(event_name: str, event: dict) -> int:
    # PR_NUMBER env var tiene prioridad (viene del paso ctx del workflow)
    pr_env = os.environ.get("PR_NUMBER", "").strip()
    if pr_env:
        return int(pr_env)
    if event_name in ("pull_request", "pull_request_target"):
        return int(event["pull_request"]["number"])
    print(f"[ERROR] No se pudo obtener PR number para evento: {event_name}", file=sys.stderr)
    sys.exit(1)


def fetch_pr_diff(repo: str, pr_number: int, token: str) -> str:
    url = f"{GITHUB_API}/repos/{repo}/pulls/{pr_number}"
    headers = github_headers(token)
    headers["Accept"] = "application/vnd.github.v3.diff"
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.text.strip()


def call_gemini(prompt: str, api_key: str, model_name: str):
    client = _genai.Client(api_key=api_key)
    return client.models.generate_content(
        model=f"models/{model_name}",
        contents=prompt,
        config=_gtypes.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=8192,
        ),
    )


def get_token_counts(response) -> tuple:
    """Devuelve (input_tokens, output_tokens, cached_tokens). output_tokens incluye
    candidates + thinking (Google los billea igual)."""
    meta = getattr(response, "usage_metadata", None)
    if meta is None:
        return 0, 0, 0
    in_t = int(getattr(meta, "prompt_token_count", 0) or 0)
    cached_t = int(getattr(meta, "cached_content_token_count", 0) or 0)
    out_t = getattr(meta, "candidates_token_count", None) or 0
    thoughts_t = getattr(meta, "thoughts_token_count", None) or 0
    out_t = int(out_t) + int(thoughts_t)
    if out_t == 0:
        total = int(getattr(meta, "total_token_count", 0) or 0)
        out_t = max(0, total - in_t)
    return in_t, out_t, cached_t


def get_real_model(response, requested_model: str) -> str:
    """El modelo que REALMENTE corrio segun la API, no el que pedimos - Google
    puede alias-ear en runtime (confirmado con gemini-2.5-flash -> gemini-3.5-flash)."""
    version = getattr(response, "model_version", None)
    if not version:
        return requested_model
    version = version.replace("models/", "")
    for known in sorted(MODEL_PRICING, key=len, reverse=True):
        if version == known or version.startswith(known + "-") or version.startswith(known):
            return known
    return version


def calculate_cost(model: str, input_tok: int, output_tok: int, cached_tok: int) -> float:
    pricing = MODEL_PRICING.get(model, DEFAULT_PRICING)
    billable_input = max(0, input_tok - cached_tok)
    return (
        billable_input * pricing["input"]
        + cached_tok * pricing["cache"]
        + output_tok * pricing["output"]
    ) / 1_000_000


def post_cost_comment(repo: str, pr_number: int, token: str, requested_model: str,
                       real_model: str, input_tok: int, output_tok: int,
                       cached_tok: int, cost: float) -> None:
    model_label = f"`{real_model}`"
    if real_model != requested_model:
        model_label = f"`{real_model}` ⚠️ (se pidió `{requested_model}`, Google lo alias-eó en runtime)"
    body = (
        "<!-- gemini-cost-report -->\n"
        f"💰 **Costo real de esta transacción Gemini** ({model_label}): **${cost:.4f} USD**\n\n"
        "| Tokens input (sin cache) | Tokens desde cache | Tokens output (respuesta + thinking) |\n"
        "|---|---|---|\n"
        f"| {max(0, input_tok - cached_tok)} | {cached_tok} | {output_tok} |\n\n"
        "_Calculado con precios oficiales por millón de tokens vigentes al momento de este PR — "
        "verificar en [ai.google.dev/gemini-api/docs/pricing](https://ai.google.dev/gemini-api/docs/pricing) "
        "si cambiaron._"
    )
    url = f"{GITHUB_API}/repos/{repo}/issues/{pr_number}/comments"
    resp = requests.post(url, headers=github_headers(token), json={"body": body}, timeout=30)
    resp.raise_for_status()


def post_github_comment(repo: str, pr_number: int, token: str, event: str, body: str) -> None:
    url = f"{GITHUB_API}/repos/{repo}/pulls/{pr_number}/reviews"
    # APPROVE no funciona si eres el autor del PR, siempre usamos COMMENT o REQUEST_CHANGES
    if event == "APPROVE":
        event = "COMMENT"
    resp = requests.post(
        url, headers=github_headers(token),
        json={"body": body, "event": event}, timeout=30,
    )
    resp.raise_for_status()


def save_corrected_files(raw: str) -> bool:
    matches = FILE_RE.findall(raw)
    if not matches:
        return False
    for file_path, content in matches:
        dir_name = os.path.dirname(file_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as fh:
            fh.write(content)
        print(f"[INFO] Corregido: {file_path}", file=sys.stderr)
    return True


def write_github_output(key: str, value: str) -> None:
    output_file = os.environ.get("GITHUB_OUTPUT", "")
    if output_file:
        with open(output_file, "a", encoding="utf-8") as fh:
            fh.write(f"{key}={value}\n")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    gemini_key = get_env("GEMINI_API_KEY")
    gh_token   = get_env("GITHUB_TOKEN")
    event_name = get_env("GITHUB_EVENT_NAME")
    repository = get_env("GITHUB_REPOSITORY")
    model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip()

    with open(get_env("GITHUB_EVENT_PATH"), encoding="utf-8") as fh:
        event_payload = json.load(fh)

    pr_num = resolve_pr_number(event_name, event_payload)
    print(f"[INFO] Revisando PR #{pr_num} con {model_name}", file=sys.stderr)

    diff = fetch_pr_diff(repository, pr_num, gh_token)
    if not diff:
        print("[WARN] Diff vacío. Sin cambios que revisar.", file=sys.stderr)
        write_github_output("verdict", "APROBADO")
        return

    prompt = f"{SYSTEM_PROMPT}\n\nAnaliza y corrige este diff:\n\n```diff\n{diff}\n```"

    print(f"[INFO] Consultando {model_name}...", file=sys.stderr)
    try:
        response = call_gemini(prompt, gemini_key, model_name)
    except Exception as exc:
        print(f"[ERROR] Fallo en la API de Gemini: {exc}", file=sys.stderr)
        sys.exit(1)

    raw = response.text

    real_model = get_real_model(response, model_name)
    in_tok, out_tok, cached_tok = get_token_counts(response)
    cost = calculate_cost(real_model, in_tok, out_tok, cached_tok)
    if real_model != model_name:
        print(f"[WARN] Se pidio '{model_name}' pero corrio '{real_model}' - Google lo alias-eo en runtime.", file=sys.stderr)
    print(
        f"[INFO] Tokens — input: {in_tok} (cache: {cached_tok}), output: {out_tok} | "
        f"Costo real: ${cost:.6f} USD ({real_model})",
        file=sys.stderr,
    )
    try:
        post_cost_comment(repository, pr_num, gh_token, model_name, real_model, in_tok, out_tok, cached_tok, cost)
    except Exception as exc:
        print(f"[WARN] No se pudo postear el comentario de costo: {exc}", file=sys.stderr)

    # Extraer veredicto
    match = VERDICT_RE.search(raw)
    verdict = match.group(1).upper() if match else "APROBADO"

    # Texto limpio (sin bloques <file> ni veredicto)
    clean = VERDICT_RE.sub("", raw)
    clean = FILE_RE.sub("", clean).strip()

    if verdict == "CORREGIDO":
        saved = save_corrected_files(raw)
        if saved:
            body = (
                f"## 🛠️ Correcciones automáticas — {model_name}\n\n"
                "Se han detectado problemas críticos. **PR bloqueado.**\n"
                "Se abrirá un PR automático con los cambios corregidos. Revísalo antes de mergear.\n\n"
                f"### Análisis:\n{clean}"
            )
            post_github_comment(repository, pr_num, gh_token, "REQUEST_CHANGES", body)
            print("[OK] Archivos corregidos. PR bloqueado. Actions creará el PR de fixes.", file=sys.stderr)
        else:
            print("[WARN] Veredicto CORREGIDO pero sin bloques <file>. Bloqueando igualmente.", file=sys.stderr)
            body = (
                f"## 🚨 Problemas críticos detectados — {model_name}\n\n"
                "**PR bloqueado.** Se detectaron problemas críticos pero no fue posible "
                "generar la corrección automática. Corrige manualmente antes de mergear.\n\n"
                f"### Detalles:\n{clean}"
            )
            post_github_comment(repository, pr_num, gh_token, "REQUEST_CHANGES", body)

    elif verdict == "ESTRUCTURAL":
        body = (
            f"## 🏗️ Problemas estructurales — {model_name}\n\n"
            "**PR bloqueado.** El código necesita refactorización antes de mergearse. "
            "Los cambios requeridos implican partes del proyecto fuera de este diff, "
            "por lo que deben aplicarse manualmente.\n\n"
            f"### Qué hay que hacer:\n{clean}"
        )
        post_github_comment(repository, pr_num, gh_token, "REQUEST_CHANGES", body)
        print("[OK] PR bloqueado por problemas estructurales.", file=sys.stderr)

    elif verdict == "COMENTAR":
        body = f"## 💬 Sugerencias de mejora — {model_name}\n\nEl PR puede mergearse. Considera estos puntos:\n\n{clean}"
        post_github_comment(repository, pr_num, gh_token, "COMMENT", body)
        print("[OK] Comentarios enviados al PR.", file=sys.stderr)

    else:  # APROBADO
        if clean:
            body = (
                f"## ✅ Aprobado — {model_name}\n\n"
                f"El código está listo para mergear. Sugerencias opcionales:\n\n{clean}"
            )
        else:
            body = f"## ✅ Aprobado — {model_name}\n\nTodo correcto. No se requieren cambios."
        post_github_comment(repository, pr_num, gh_token, "APPROVE", body)
        print("[OK] PR aprobado.", file=sys.stderr)

    write_github_output("verdict", verdict)
    print(f"[RESULTADO] Veredicto final: {verdict}", file=sys.stderr)


if __name__ == "__main__":
    main()
