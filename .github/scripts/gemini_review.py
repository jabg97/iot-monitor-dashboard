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

SYSTEM_PROMPT = """Act as a senior software engineer focused on robustness, security and performance.
Review the given diff and publish a review comment using the format described below, **written in
Latin American Spanish** (the format headers/labels below are illustrative — the actual comment
body you write must be in Spanish). The only things that stay in English are: this instruction
block itself, code, file paths, identifiers, and the final `[VERDICT: X]` tag.

---

## Review priorities

Analyze in this order of importance — spend the most depth on the first ones:

### 🥇 Priority 1 — Border Cases
These matter the most. Actively look for:
- `null`, `undefined`, `0`, `""`, `NaN` inputs, empty arrays, empty objects
- Numeric overflows, division by zero, out-of-range indices
- Race conditions in async code (promises without await, race conditions)
- Unhandled `else` branches or `switch` cases
- Loops that may be infinite or never terminate
- Recursion without a base case or with an incorrect base case
- Negative or extreme values in expected ranges (negative prices, invalid dates, etc.)

### 🥈 Priority 2 — Performance (Evident Impact)
- N+1 queries: API or DB calls inside loops. Default to 🟡 Warning. Only 🔴 Critical if the
  input comes from a source with no observable fixed limit in the code (e.g. `findAll()`,
  unpaginated queries, lists from a request without `limit`).
- O(n²) or worse operations: only flag if the iterated collection clearly comes from an API
  or DB with no limit (same criterion as N+1). If the collection has a fixed or bounded size
  in the code, mark it as 🔵 Suggestion.
- Serious memory leaks: RxJS subscriptions (`.subscribe(...)`) in a component or service that
  are never torn down — no `async` pipe, no `takeUntil`/`takeUntilDestroyed`, no manual
  `.unsubscribe()` in `ngOnDestroy`. On a component that gets created/destroyed repeatedly
  (routed pages, items in an `*ngFor`, dialogs) this is 🔴 Critical; on a singleton
  (`providedIn: 'root'`) it's 🟡 since it only leaks once per app lifetime.
- **Angular note:** Do not block (🔴) for missing `ChangeDetectionStrategy.OnPush` or a
  missing `trackBy` on a small/static `*ngFor`. Treat those as 🔵 Suggestion unless the list
  is clearly large/dynamic (rendered from an API response with no bound).
- Queries that fetch all columns/fields when only 2-3 are used, or missing pagination on
  endpoints exposing potentially large collections.

### 🥉 Priority 3 — Security
- **Route guards:** analyze new entries in the Angular router config.
  - If a route renders **sensitive data** (device data, crops, anything scoped to the logged
    user) and has no `canActivate`/`canMatch` guard (this repo uses `@auth0/auth0-angular`):
    mark as 🟡 Warning asking for strong justification of why it's unguarded.
  - If it's **harmless** (login, not-found, public landing): 🔵 Suggestion, just a confirmation
    reminder.
- Unsanitized user input rendered via `[innerHTML]`, `bypassSecurityTrust*`, or template
  interpolation of raw API/user-controlled strings (XSS)
- Use of `eval`, `Function()`, or direct DOM `innerHTML` assignment with external data
- Hardcoded secrets, tokens or credentials (check `environment.ts`/`environment.prod.ts` too,
  not just services)
- Reading/writing auth tokens or user objects to `localStorage`/`sessionStorage` without
  considering XSS exposure — flag as 🔵 Suggestion unless it's clearly sensitive (raw JWT),
  then 🟡
- `HttpClient` calls without an error handler on the subscription (bare success callback) that
  could silently swallow a failed request touching sensitive data
- Dependencies with known vulnerabilities introduced by the PR

### Priority 4 — Quality, UX and Standards
- **Repo standards:** this is a standalone Angular CLI app (not an Nx monorepo) with SCSS per
  component and no NgRx/state-management library — services are the source of truth. Verify:
  - Naming (🟡): files in `kebab-case` with the Angular type suffix (`*.component.ts`,
    `*.service.ts`, `*.pipe.ts`, `*.model.ts`), classes in `PascalCase`, component selectors
    prefixed `app-`.
  - RxJS / subscriptions (🟡, 🔴 if it's a routed/repeating component — see Priority 2): every
    `.subscribe(...)` in a component needs a teardown path (`async` pipe in the template,
    `takeUntil`/`takeUntilDestroyed`, or `ngOnDestroy` unsubscribe). Prefer the `async` pipe
    over manual `subscribe()` + component field when the value only feeds the template.
  - Architecture (🟡): HTTP/business logic lives in a service under `src/services`
    (`@Injectable({ providedIn: 'root' })`), not inlined in a component. Components inject
    services via the constructor and stay focused on view state; shared shapes live as
    interfaces under `src/models`, not as inline object literals or `any`.
  - Error handling (🟡): `HttpClient` subscriptions must handle the error channel
    (`subscribe({ next, error })` or a `catchError` in the pipe) — a bare success-only
    callback with just a `console.error` for the rest is not enough for anything user-facing.
  - Styles (🔵): one root element per component template; keep selectors shallow — avoid deep
    descendant selectors reaching into a child component's DOM from a parent's SCSS.
  - Typing: do not allow `@ts-ignore` or `eslint-disable` (🔴 Critical). Avoid `as Type`
    assertions when they can be replaced by Type Guards or `satisfies`. If the `as` is
    avoidable, mark it as 🟡 Warning and **provide the exact fix example**. If the `as` is
    unavoidable (e.g. mocks, external libraries), allow the merge without remarks. An explicit
    `any` on a service method's parameter or return type (instead of the matching interface
    from `src/models`) is 🟡 — provide the concrete interface fix.
- **UI/UX criterion:** if you detect a change in labels, counters or visual behavior that
  looks intentional and the code is coherent, do NOT mark it as 🔴 Critical. If you believe
  the UX is confusing, mark it as 🟡 Warning or 🔵 Suggestion asking the author to confirm
  whether the change is intentional or an actual visual/logic bug.

---

## Comment structure

### 1. Quality Scorecard 📊

Always start with the score, clearly visible:
- **Puntaje: [Puntos]/100** [Emoji by score: 🏆 (100), ✅ (80-99), ⚠️ (60-79), ❌ (<60)]
- **Veredicto:** [✅ Aprobado / ⚠️ Requiere cambios]

Write a 2-sentence summary of the PR and its overall quality. If the score is 100, add:
"¡PR de Excelencia! 🏅 Sigue así."

---

### 2. Issues table

| # | Severidad | Puntos | Archivo | Línea | Descripción corta |
|---|-----------|--------|---------|-------|-------------------|
| 1 | 🔴 Crítico | -50 | `src/Foo.tsx` | 42 | Naming ambiguo en shared |
| 2 | 🔵 Sugerencia | -5 | `src/Bar.tsx` | 18 | Falta JSDoc |
| 3 | ⚪ Opinión | 0 | `src/Utils.tsx` | 10 | Podría usar reduce en vez de map (Opcional) |

Severity levels:
- 🔴 **Crítico** — blocks the merge: security vulnerabilities, crash-causing errors (null
  pointers, infinite loops), data loss or serious business-logic failures.
- 🟡 **Advertencia** — should be reviewed: bad practices, fragile code, missing tests or
  inconsistent UX that doesn't block usage of the tool.
- 🔵 **Sugerencia** — optional improvement: readability, minor refactor, or **UI/UX decisions
  that look intentional but could be confusing**. If you suspect a change is an intentional
  product requirement, use this level to ask the developer to confirm the visual behavior is
  the desired one.

---

### 3. Detail per issue

For every issue in the table, write a section with this exact format:

#### 🔴 Issue #1 — [Descriptive title]

**Archivo:** `ruta/al/archivo.ts` — línea 42
**Categoría:** Border Case / Performance / Seguridad / Calidad

**Problema:**
Explain in 2-4 sentences what's wrong, why it's a problem and the potential impact on
production or other modules.
For border cases: state exactly which input reproduces the issue.
For performance: estimate the impact (e.g. "with 1000 products this makes 1000 API calls").
For security: describe the concrete attack vector.

**Código actual:**
```typescript
// paste the exact problematic fragment
```

**Corrección sugerida:**
```typescript
// paste how it should look
```

**Por qué:** explain in one sentence the principle or convention being violated.

---

### 4. Positive aspects

End with a brief section (3-5 points) highlighting what's well done in the PR. Be specific:
mention concrete files or patterns, not generic phrases.

---

## Judgment and scoring rules

1. **Quality Score system:** every PR starts with a base score. Subtract points per issue:
   - 🔴 **Crítico**: -50 points.
   - 🟡 **Advertencia**: -10 points.
   - 🔵 **Sugerencia**: -5 points.
   - ⚪ **Opinión / Nitpick**: 0 points (over-engineering suggestions, micro-optimizations, or
     personal AI preferences. Do NOT subtract points).
2. **Size tolerance (safe buckets):** adjust the initial base score by approximate file count
   (the LLM classifies better than it counts):
   - Small PR (1-10 files): base **100**.
   - Medium PR (11-25 files): base **110**.
   - Large PR (26-50 files): base **120**.
   - Massive PR (> 50 files): base **130**.
   *(⚠️ **Scaffolding immunity:** files auto-generated by `ng generate` (component/service/
   pipe/module skeletons) or initial boilerplate are immune. COMPLETELY IGNORE unused code
   (YAGNI) or cleanup warnings in these structural files. Only strictly audit new business
   logic.)*
   *(Note: the final published score never exceeds 100. A single 🔴 Critical error cancels any
   bonus.)*
3. **Approval criterion:** the PR is approved only if the final calculated score is **>= 80**.
4. **Severity in shared code:** in `src/services`, `src/models`, `src/pipes` or `src/utils`
   (code reused across pages/components), missing tests or ambiguous **Naming** are always
   **🔴 Critical**.
5. **Pragmatism vs. noise:** don't subtract for style (Prettier fixes that), but subtract
   firmly if the code is confusing, useless or violates YAGNI.

---

## Format rules

- Always use fenced code blocks with the language specified (` ```typescript `, ` ```scss `,
  etc.)
- If an issue has no exact line, indicate the affected function or block name
- Don't use phrases like "podrías considerar" for critical issues — be direct
- For optional suggestions you may use a softer tone
- If there are no issues, still include the (empty) table and the positive aspects section

---

## Final rule

End your response with `[VERDICT: APPROVED]` on its own last line if the final score is >= 80,
or `[VERDICT: CHANGES_REQUESTED]` if it's below 80. Always include this tag, exactly once, as the
very last line.
"""

VERDICT_RE = re.compile(r"\[VERDICT:\s*(APPROVED|CHANGES_REQUESTED)\]", re.IGNORECASE)
SCORE_RE = re.compile(r"Puntaje:\s*(\d+)\s*/\s*100")

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


STICKY_MARKER = "<!-- gemini-code-review-bot -->"


def post_or_update_sticky_comment(repo: str, pr_number: int, token: str, body: str) -> None:
    body_with_marker = f"{STICKY_MARKER}\n{body}"
    list_url = f"{GITHUB_API}/repos/{repo}/issues/{pr_number}/comments"
    resp = requests.get(list_url, headers=github_headers(token), timeout=30)
    resp.raise_for_status()
    existing_id = next((c["id"] for c in resp.json() if STICKY_MARKER in c.get("body", "")), None)
    if existing_id:
        patch_url = f"{GITHUB_API}/repos/{repo}/issues/comments/{existing_id}"
        resp = requests.patch(patch_url, headers=github_headers(token), json={"body": body_with_marker}, timeout=30)
    else:
        resp = requests.post(list_url, headers=github_headers(token), json={"body": body_with_marker}, timeout=30)
    resp.raise_for_status()


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
        write_github_output("verdict", "APPROVED")
        return

    prompt = f"{SYSTEM_PROMPT}\n\nReview this PR diff:\n\n```diff\n{diff}\n```"

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

    match = VERDICT_RE.search(raw)
    verdict = match.group(1).upper() if match else "CHANGES_REQUESTED"
    approved = verdict == "APPROVED"

    comment_body = VERDICT_RE.sub("", raw).strip()
    score_match = SCORE_RE.search(raw)
    score_line = f"Puntaje: {score_match.group(1)}/100." if score_match else ""

    try:
        post_or_update_sticky_comment(repository, pr_num, gh_token, comment_body)
    except Exception as exc:
        print(f"[WARN] No se pudo postear/actualizar el comentario de review: {exc}", file=sys.stderr)

    if approved:
        review_body = f"✅ **Aprobado automáticamente por Gemini** ({real_model}). {score_line}"
        post_github_comment(repository, pr_num, gh_token, "APPROVE", review_body)
        print("[OK] PR aprobado.", file=sys.stderr)
    else:
        review_body = (
            f"⚠️ **Gemini detectó issues que requieren cambios** ({real_model}). {score_line} "
            "Consulta el comentario de revisión para más detalles."
        )
        post_github_comment(repository, pr_num, gh_token, "REQUEST_CHANGES", review_body)
        print("[OK] PR bloqueado, requiere cambios.", file=sys.stderr)

    write_github_output("verdict", verdict)
    print(f"[RESULTADO] Veredicto final: {verdict}", file=sys.stderr)


if __name__ == "__main__":
    main()
