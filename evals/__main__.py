"""Corre todos los casos de evaluación y reporta el puntaje del agente.

Uso:
    python -m evals
Escribe evals/resultados.md. Termina con error si el puntaje baja del mínimo (sirve para la CI).
"""

import os
import sys
import time
from datetime import datetime

from dotenv import load_dotenv

from evals.calificar import calificar
from evals.casos import CASOS

PUNTAJE_MINIMO = 0.80
PAUSA = float(os.getenv("EVAL_PAUSA", "5"))   # segundos entre preguntas (el nivel gratuito tiene límite por minuto)


def main():
    load_dotenv()
    from agente.agente import AgenteGemini, CuotaAgotada

    agente = AgenteGemini()
    filas, aprobados, modelos = [], 0, set()

    for i, caso in enumerate(CASOS, 1):
        inicio = time.time()
        try:
            texto, llamadas = agente.responder(caso["pregunta"])
            ok, motivo = calificar(caso, texto, llamadas)
            modelos.add(getattr(agente, "modelo_usado", "?"))
        except CuotaAgotada as error:
            print(f"\n⛔ {error} Evaluación detenida en la pregunta {i}.")
            break
        except Exception as error:
            texto, llamadas, ok, motivo = "", [], False, f"error: {str(error)[:120]}"
        segundos = time.time() - inicio
        aprobados += ok
        herramientas = ", ".join(l["herramienta"] for l in llamadas) or "—"
        print(f"{'✅' if ok else '❌'} {i:2}/{len(CASOS)} {caso['id']:<16} {motivo}  [{herramientas}] {segundos:.1f}s")
        filas.append((caso, ok, motivo, herramientas, segundos, texto))
        if i < len(CASOS):
            time.sleep(PAUSA)

    if len(filas) < len(CASOS):
        print(f"Se evaluaron {len(filas)} de {len(CASOS)} casos; no se guardan resultados parciales.")
        sys.exit(2)
    puntaje = aprobados / len(CASOS)
    print(f"\nPuntaje: {aprobados}/{len(CASOS)} = {puntaje:.0%} (mínimo {PUNTAJE_MINIMO:.0%})")

    with open("evals/resultados.md", "w", encoding="utf-8") as f:
        f.write(f"# Resultados de evaluación\n\nModelo: `{', '.join(sorted(modelos)) or '?'}` · {datetime.now():%Y-%m-%d %H:%M} · "
                f"**{aprobados}/{len(CASOS)} ({puntaje:.0%})**\n\n")
        f.write("| Caso | Pregunta | Resultado | Herramientas | Tiempo |\n|---|---|---|---|---|\n")
        for caso, ok, motivo, herramientas, segundos, _ in filas:
            f.write(f"| {caso['id']} | {caso['pregunta']} | {'✅' if ok else '❌'} {motivo} | "
                    f"{herramientas} | {segundos:.1f}s |\n")

    sys.exit(0 if puntaje >= PUNTAJE_MINIMO else 1)


if __name__ == "__main__":
    main()
