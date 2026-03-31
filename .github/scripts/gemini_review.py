"""
Gemini AI Code Review Script
Fetches the diff of a GitHub Pull Request and submits an official
GitHub review based on Gemini 1.5 Flash's analysis.
"""

import json
import os
import re
import sys

from google import genai
from google.genai import types
import requests

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """Eres un Senior Engineer especializado en Angular (v14+) y TypeScript. \
Tu misión es hacer una revisión exhaustiva del diff que se te proporciona, actuando como si fuera \
una code review real antes de mergear a producción. Evalúa los siguientes aspectos en orden de prioridad:

1. **Seguridad**
   - Detecta vulnerabilidades conocidas en dependencias nuevas o actualizadas en package.json/package-lock.json \
(busca versiones con CVEs públicos o rangos demasiado abiertos como `*` o `>=0.0.0`).
   - Identifica XSS potencial: uso de `innerHTML`, `bypassSecurityTrust*`, o `[innerHTML]` sin sanitizar.
   - Detecta secretos, API keys o tokens hardcodeados.
   - Señala uso inseguro de `localStorage`/`sessionStorage` con datos sensibles.

2. **Buenas prácticas de Angular**
   - Verifica que los componentes usen `OnPush` Change Detection cuando sea posible.
   - Detecta subscripciones a Observables sin `takeUntil`, `async pipe`, o `takeUntilDestroyed` (memory leaks).
   - Revisa que los módulos no sean innecesariamente grandes (considera lazy loading).
   - Evalúa si se usa correctamente la inyección de dependencias (`inject()` vs constructor) de forma consistente.
   - Detecta lógica de negocio en componentes que debería estar en servicios.
   - Verifica el uso correcto de `TrackBy` en `*ngFor` para evitar re-renders innecesarios.

3. **Calidad TypeScript**
   - Penaliza el uso de `any` explícito donde se puede inferir o definir un tipo concreto.
   - Detecta type assertions forzadas (`as SomeType`) que ocultan errores potenciales.
   - Señala funciones demasiado largas (más de ~40 líneas) que deberían descomponerse.
   - Identifica lógica duplicada o código que puede simplificarse con operadores RxJS, \
`optional chaining` (`?.`), `nullish coalescing` (`??`) o utilidades de TypeScript.
   - Detecta `console.log` o código de debug olvidado.

4. **Rendimiento**
   - Detecta llamadas HTTP innecesarias dentro de bucles o sin debounce en inputs.
   - Señala importaciones de módulos completos cuando solo se necesita un subconjunto (tree-shaking).
   - Identifica Pipes impuras donde debería usarse una pura.

5. **Tolerancia contextual**
   - Si el cambio es puramente de estilos (CSS/SCSS), textos en plantillas HTML o configuración menor, \
sé tolerante y no bloquees el PR salvo que haya un problema real.

6. **Evaluación de complejidad e impacto** *(criterio para el veredicto final)*
   Antes de emitir el veredicto, evalúa la magnitud del cambio:
   - **Cambio simple o aislado** (un componente pequeño, un modelo, un pipe, CSS): decide directamente \
→ APROBADO si está bien, o RECHAZADO si tiene errores claros.
   - **Cambio moderado** (un servicio con lógica de negocio, refactor de un módulo): emite COMENTARIO \
con sugerencias puntuales si no hay bloqueantes.
   - **Cambio extenso o de alto impacto** (modifica flujos críticos como autenticación, comunicación con \
dispositivos IoT, rutas principales, lógica de estado global, o toca más de 10 archivos con cambios \
sustanciales): emite REVISION_HUMANA aunque no detectes errores evidentes. Explica por qué la \
complejidad supera lo que un análisis estático puede garantizar con seguridad.

---
Formatea tu respuesta usando Markdown con secciones claras por categoría. \
Si no encuentras problemas en una categoría, indícalo brevemente. \
Sé directo, conciso y accionable: indica el archivo y línea si es posible.

Al final de tu respuesta, en una línea separada, DEBES incluir obligatoriamente uno de estos cuatro veredictos:
[VEREDICTO: APROBADO] → Cambio simple/moderado, correcto y seguro, se puede mergear sin intervención humana.
[VEREDICTO: RECHAZADO] → Hay problemas críticos de seguridad, bugs evidentes o malas prácticas graves.
[VEREDICTO: COMENTARIO] → Hay sugerencias de mejora menores pero ningún bloqueante crítico.
[VEREDICTO: REVISION_HUMANA] → El cambio es demasiado extenso o complejo para garantizar su corrección \
solo con análisis estático. Se requiere revisión manual por parte de un desarrollador.
"""

VERDICT_PATTERN = re.compile(
    r"\[VEREDICTO:\s*(APROBADO|RECHAZADO|COMENTARIO|REVISION_HUMANA)\]",
    re.IGNORECASE,
)

VERDICT_TO_EVENT = {
    "APROBADO": "APPROVE",
    "RECHAZADO": "REQUEST_CHANGES",
    "COMENTARIO": "COMMENT",
    "REVISION_HUMANA": "COMMENT",  # GitHub API only supports APPROVE/REQUEST_CHANGES/COMMENT
}

GITHUB_API = "https://api.github.com"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def get_env(name: str) -> str:
    """Return a required environment variable or exit with an error."""
    value = os.environ.get(name, "").strip()
    if not value:
        print(f"[ERROR] Missing required environment variable: {name}", file=sys.stderr)
        sys.exit(1)
    return value


def github_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def resolve_pull_number(event_name: str, event: dict) -> int:
    """
    Resolve the PR number from the GitHub event payload.
    Handles both pull_request / pull_request_target events and issue_comment events.
    """
    if event_name in ("pull_request", "pull_request_target"):
        pr_number = event.get("pull_request", {}).get("number")
        if pr_number:
            return int(pr_number)

    if event_name == "issue_comment":
        # The PR number lives under event.issue.number when the comment is on a PR
        pr_number = event.get("issue", {}).get("number")
        if pr_number:
            return int(pr_number)

    print(
        f"[ERROR] Could not resolve PR number from event '{event_name}'.",
        file=sys.stderr,
    )
    sys.exit(1)


def fetch_pr_diff(repo: str, pr_number: int, token: str) -> str:
    """Fetch the unified diff of a Pull Request via the GitHub API."""
    url = f"{GITHUB_API}/repos/{repo}/pulls/{pr_number}"
    headers = github_headers(token)
    headers["Accept"] = "application/vnd.github.v3.diff"

    response = requests.get(url, headers=headers, timeout=30)
    if response.status_code != 200:
        print(
            f"[ERROR] Failed to fetch PR diff: {response.status_code} {response.text}",
            file=sys.stderr,
        )
        sys.exit(1)

    diff = response.text.strip()
    if not diff:
        print("[WARN] PR diff is empty. Nothing to review.")
        sys.exit(0)

    return diff


def analyze_diff_with_gemini(diff: str, api_key: str) -> str:
    """Send the diff to Gemini 1.5 Flash using the modern google.genai Client."""
    client = genai.Client(api_key=api_key)

    prompt = f"A continuación está el diff del Pull Request para que lo analices:\n\n```diff\n{diff}\n```"

    try:
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.2,
                max_output_tokens=4096,
            )
        )
    except Exception as e:
        print(f"[ERROR] Gemini API call failed: {e}", file=sys.stderr)
        sys.exit(1)

    if not response or not response.text:
        print("[ERROR] Gemini returned an empty response.", file=sys.stderr)
        sys.exit(1)

    return response.text


def parse_verdict(gemini_text: str) -> tuple[str, str]:
    """
    Extract the verdict label from Gemini's response.
    Returns (verdict_key, body_without_verdict_line).
    """
    match = VERDICT_PATTERN.search(gemini_text)
    if not match:
        # Default to COMMENT when no structured verdict is found
        print("[WARN] No structured verdict found in Gemini response; defaulting to COMENTARIO.")
        return "COMENTARIO", gemini_text.strip()

    verdict_key = match.group(1).upper()
    # Remove the verdict line from the body shown as the PR review body
    body = VERDICT_PATTERN.sub("", gemini_text).strip()
    return verdict_key, body


def submit_github_review(
    repo: str,
    pr_number: int,
    token: str,
    event: str,
    body: str,
) -> None:
    """Post an official GitHub review to the Pull Request."""
    url = f"{GITHUB_API}/repos/{repo}/pulls/{pr_number}/reviews"

    payload = {
        "body": body,
        "event": event,
    }

    response = requests.post(
        url,
        headers=github_headers(token),
        json=payload,
        timeout=30,
    )

    if response.status_code not in (200, 201):
        print(
            f"[ERROR] Failed to submit GitHub review: {response.status_code} {response.text}",
            file=sys.stderr,
        )
        sys.exit(1)

    review_data = response.json()
    review_id = review_data.get("id", "unknown")
    print(f"[OK] GitHub review submitted successfully (id={review_id}, event={event}).")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    # -- Read environment variables ------------------------------------------
    gemini_api_key = get_env("GEMINI_API_KEY")
    github_token = get_env("GITHUB_TOKEN")
    event_name = get_env("GITHUB_EVENT_NAME")
    repository = get_env("GITHUB_REPOSITORY")
    event_path = get_env("GITHUB_EVENT_PATH")

    # -- Load the GitHub event payload ----------------------------------------
    try:
        with open(event_path, encoding="utf-8") as fh:
            event_payload = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[ERROR] Could not read event payload from {event_path}: {exc}", file=sys.stderr)
        sys.exit(1)

    # -- Resolve PR number ----------------------------------------------------
    pr_number = resolve_pull_number(event_name, event_payload)
    print(f"[INFO] Reviewing PR #{pr_number} in {repository} (trigger: {event_name})")

    # -- Fetch the diff -------------------------------------------------------
    print("[INFO] Fetching PR diff from GitHub API...")
    diff = fetch_pr_diff(repository, pr_number, github_token)
    print(f"[INFO] Diff fetched ({len(diff)} characters).")

    # -- Analyse with Gemini --------------------------------------------------
    print("[INFO] Sending diff to Gemini 1.5 Flash for analysis...")
    gemini_response = analyze_diff_with_gemini(diff, gemini_api_key)
    print("[INFO] Gemini analysis complete.")

    # -- Parse verdict --------------------------------------------------------
    verdict_key, review_body = parse_verdict(gemini_response)
    github_event = VERDICT_TO_EVENT.get(verdict_key, "COMMENT")
    print(f"[INFO] Verdict: {verdict_key} → GitHub event: {github_event}")

    # -- Build the final review body with a header ---------------------------
    # For REVISION_HUMANA we use a distinct emoji and banner regardless of GitHub event
    is_human_review = verdict_key == "REVISION_HUMANA"
    verdict_emoji = (
        "🔍"
        if is_human_review
        else {"APPROVE": "✅", "REQUEST_CHANGES": "❌", "COMMENT": "💬"}.get(github_event, "💬")
    )
    human_review_banner = (
        "\n\n> ⚠️ **Se requiere revisión humana.** Este PR involucra cambios extensos o de alta "
        "complejidad que superan lo que el análisis estático puede garantizar. "
        "Por favor, asigna un revisor manualmente.\n"
        if is_human_review
        else ""
    )
    final_body = (
        f"## {verdict_emoji} Gemini AI Code Review\n\n"
        f"{review_body}"
        f"{human_review_banner}\n\n"
        f"---\n"
        f"*Revisión automatizada generada por [Gemini 1.5 Flash](https://deepmind.google/technologies/gemini/).*"
    )

    # -- Submit GitHub review -------------------------------------------------
    print("[INFO] Submitting official GitHub review...")
    submit_github_review(repository, pr_number, github_token, github_event, final_body)


if __name__ == "__main__":
    main()
