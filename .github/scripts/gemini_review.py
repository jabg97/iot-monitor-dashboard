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

SYSTEM_PROMPT = """Eres un Senior Full-Stack Engineer experto en Angular (v14+) y TypeScript.
Tu misión es revisar el diff proporcionado y clasificarlo en exactamente uno de estos 4 veredictos.
Lee todos los criterios antes de decidir. Aplica siempre el veredicto de mayor gravedad que encuentres.

════════════════════════════════════════════════════════
VEREDICTO: CORREGIDO  →  bloquea el PR + genera el código corregido automáticamente
════════════════════════════════════════════════════════
Úsalo SOLO cuando el problema está contenido en los archivos del diff y puedes reescribirlos
correctamente sin necesidad de conocer el resto del proyecto. Casos:

  • Bug que rompe funcionalidad en runtime (null pointer, condición invertida, lógica errónea)
  • Vulnerabilidad de seguridad (XSS, inyección HTML/SQL/JS, datos sensibles en logs o templates,
    CSRF, tokens expuestos en frontend)
  • Memory leak por suscripción Observable sin takeUntil, sin unsubscribe o sin async pipe,
    cuando el patrón correcto es visible en el propio diff
  • Breaking change de interfaz, @Input/@Output o contrato de servicio sin retrocompatibilidad
  • Llamada a API con parámetros incorrectos que causaría error en producción
  • Bucle infinito o condición de carrera evidente

  FORMATO: explica el problema brevemente y proporciona el archivo completo corregido:

  <file path="ruta/exacta/segun/el/diff.ts">
  // código completo corregido
  </file>

════════════════════════════════════════════════════════
VEREDICTO: ESTRUCTURAL  →  bloquea el PR + explica qué refactorizar (sin generar código)
════════════════════════════════════════════════════════
Úsalo cuando el problema requiere conocer archivos fuera del diff para corregirlo bien.
Generar código aquí sería arriesgado porque podrías inventar imports o rutas incorrectas. Casos:

  • Función o método copiado/pegado que ya existe en otro lugar del proyecto
    (ves la duplicación en el diff pero el original está en otro archivo)
  • Función con más de 50 líneas que mezcla responsabilidades y debe extraerse
  • Componente con más de 300 líneas que debe dividirse en componentes hijos
  • Lógica de negocio compleja dentro del componente que debería vivir en un servicio
  • Importación del módulo completo cuando solo se usa una parte
    (ej: import * as _ from 'lodash' o import { everything } from '@angular/core')

  FORMATO: para cada problema indica exactamente —
  - Qué archivo y función/clase tiene el problema
  - Por qué es un problema (una línea)
  - Qué debe hacerse concretamente (pasos numerados, sin inventar código externo)

════════════════════════════════════════════════════════
VEREDICTO: COMENTAR  →  no bloquea + avisa de mejoras recomendadas
════════════════════════════════════════════════════════
Úsalo cuando hay cosas que mejorar pero el código funciona y puede mergearse. Casos:

  • Uso de 'any' en TypeScript sin justificación (cuando el tipo correcto es obvio)
  • *ngFor sin trackBy en listas que pueden cambiar
  • Componente que se beneficiaría de ChangeDetectionStrategy.OnPush
  • Nombre de variable o función que no expresa su intención
  • Comentario desactualizado o que explica el "qué" en lugar del "por qué"

  FORMATO: lista cada punto con archivo, línea aproximada y sugerencia concreta.

════════════════════════════════════════════════════════
VEREDICTO: APROBADO  →  aprueba el PR
════════════════════════════════════════════════════════
Úsalo cuando no hay ningún problema de los grupos anteriores.
Si ves pequeñas mejoras de estilo o legibilidad, inclúyelas como sugerencias opcionales
antes del veredicto, pero aprueba igualmente.

════════════════════════════════════════════════════════
REGLA FINAL: incluye [VEREDICTO: X] en la última línea de tu respuesta.
Si hay problemas de distintos grupos, aplica el de mayor gravedad:
CORREGIDO > ESTRUCTURAL > COMENTAR > APROBADO
════════════════════════════════════════════════════════
"""

VERDICT_RE = re.compile(r"\[VEREDICTO:\s*(APROBADO|COMENTAR|ESTRUCTURAL|CORREGIDO)\]", re.IGNORECASE)
FILE_RE = re.compile(r'<file path="([^"]+)">\s*(.*?)\s*</file>', re.DOTALL)

GITHUB_API = "https://api.github.com"

# Precios por millón de tokens (verificar en ai.google.dev/pricing)
MODEL_PRICING = {
    "gemini-2.5-flash": {"input": 0.075, "output": 0.30},
    "gemini-2.5-pro":   {"input": 1.25,  "output": 10.00},
}

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
    meta = getattr(response, "usage_metadata", None)
    if meta is None:
        return 0, 0
    in_t = int(getattr(meta, "prompt_token_count", 0) or 0)
    out_t = getattr(meta, "candidates_token_count", None)
    if out_t is None:
        total = int(getattr(meta, "total_token_count", 0) or 0)
        out_t = max(0, total - in_t)
    return in_t, int(out_t)


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

    # Costo estimado
    pricing = MODEL_PRICING.get(model_name, {"input": 0.0, "output": 0.0})
    in_tok, out_tok = get_token_counts(response)
    cost = (in_tok * pricing["input"] + out_tok * pricing["output"]) / 1_000_000
    print(
        f"[INFO] Tokens — input: {in_tok}, output: {out_tok} | "
        f"Costo estimado: ${cost:.6f} USD ({model_name})",
        file=sys.stderr,
    )

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
