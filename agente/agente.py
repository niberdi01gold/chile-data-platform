"""Agente que responde preguntas sobre indicadores económicos de Chile usando datos reales.

Uso:
    python -m agente "¿Cuánto ha subido el dólar este año?"
Requiere GEMINI_API_KEY en el archivo .env (gratis en https://aistudio.google.com)
"""

import os
import sys
import time
from datetime import date

from dotenv import load_dotenv

from agente.herramientas import DECLARACIONES, ejecutar

# Modelos del nivel gratuito, en orden de preferencia. Si uno está saturado, se usa el siguiente.
# Primero el más rápido ("lite"): elegir una herramienta y redactar una cifra no necesita el más grande.
# Los evals dicen si esa decisión es correcta.
MODELOS = [m.strip() for m in os.getenv(
    "GEMINI_MODEL", "gemini-3.5-flash-lite,gemini-3.6-flash,gemini-3.8-flash").split(",")]
MODELO = MODELOS[0]
MAX_PASOS = 6   # tope de llamadas a herramientas por pregunta: evita ciclos infinitos
TIEMPO_MAXIMO_MS = 90_000   # ninguna llamada a Gemini puede esperar más de 90 segundos


class CuotaAgotada(Exception):
    """Se acabó la cuota gratuita del día en todos los modelos: no tiene sentido seguir esperando."""

INSTRUCCIONES = """Eres un analista económico que responde preguntas sobre indicadores de Chile.
Hoy es {hoy}.

Reglas:
- Usa SIEMPRE las herramientas para obtener cifras. Nunca inventes ni uses números de memoria.
- Indica la fecha del dato que entregas.
- Para indicadores que ya son porcentaje (IPC, TPM, IMACEC, desempleo), las variaciones son en puntos.
- Si te preguntan por algo que las herramientas no tienen (otro país, bitcoin, acciones...), dilo
  claramente y no des cifras.
- Responde en español, breve y directo, con formato chileno de números (1.234,56).
"""


class AgenteGemini:
    """Conecta las herramientas con Gemini. Para usar otro proveedor, basta otra clase con 'responder'."""

    def __init__(self, cliente=None):
        from google import genai
        from google.genai import types

        self.types = types
        # Lee GEMINI_API_KEY del entorno. Los reintentos los maneja _generar (no la librería),
        # así nunca queda esperando en silencio.
        self.cliente = cliente or genai.Client(http_options=types.HttpOptions(
            timeout=TIEMPO_MAXIMO_MS, retry_options=types.HttpRetryOptions(attempts=1)))
        self.agotados = set()                        # modelos sin cuota diaria
        self.config = types.GenerateContentConfig(
            system_instruction=INSTRUCCIONES.format(hoy=date.today().isoformat()),
            tools=[types.Tool(function_declarations=[
                types.FunctionDeclaration(
                    name=d["name"], description=d["description"], parameters_json_schema=d["parameters"]
                ) for d in DECLARACIONES
            ])],
            # Control manual del ciclo: así registramos cada herramienta usada (lo necesitan los evals)
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            temperature=0,
        )

    def _generar(self, historial):
        """Llama al modelo, con modelos de respaldo:
        - saturado (503), sin respuesta a tiempo (504) o límite por minuto (429): prueba el siguiente modelo;
        - cuota DIARIA agotada: descarta ese modelo por hoy;
        - si todos fallan, espera un poco y reintenta (máximo 2 rondas)."""
        ultimo_error = None
        for ronda in range(2):
            disponibles = [m for m in MODELOS if m not in self.agotados]
            if not disponibles:
                raise CuotaAgotada("Se agotó la cuota gratuita diaria de Gemini. Intenta mañana.")
            for modelo in disponibles:
                try:
                    respuesta = self.cliente.models.generate_content(
                        model=modelo, contents=historial, config=self.config
                    )
                    self.modelo_usado = modelo
                    return respuesta
                except Exception as error:
                    texto = str(error)
                    if "429" in texto and ("PerDay" in texto or "per day" in texto.lower()):
                        self.agotados.add(modelo)     # cuota diaria: no reintentar este modelo hoy
                    elif not any(s in texto for s in ("429", "500", "503", "504", "DEADLINE", "timed out", "Timeout")):
                        raise                         # otro error (clave inválida, etc.): no sirve reintentar
                    ultimo_error = error
            if ronda == 0:
                time.sleep(10)
        if not [m for m in MODELOS if m not in self.agotados]:
            raise CuotaAgotada("Se agotó la cuota gratuita diaria de Gemini. Intenta mañana.")
        raise ultimo_error

    def responder(self, pregunta):
        """Devuelve (respuesta en texto, lista de herramientas llamadas con sus argumentos)."""
        types = self.types
        historial = [types.Content(role="user", parts=[types.Part.from_text(text=pregunta)])]
        llamadas = []

        for _ in range(MAX_PASOS):
            respuesta = self._generar(historial)
            if not respuesta.function_calls:          # ya no pide herramientas: es la respuesta final
                return respuesta.text or "", llamadas

            historial.append(respuesta.candidates[0].content)
            partes = []
            for llamada in respuesta.function_calls:
                argumentos = dict(llamada.args or {})
                resultado = ejecutar(llamada.name, argumentos)
                llamadas.append({"herramienta": llamada.name, "argumentos": argumentos})
                partes.append(types.Part.from_function_response(name=llamada.name, response=resultado))
            historial.append(types.Content(role="user", parts=partes))

        return "No pude completar la respuesta (demasiados pasos).", llamadas


def main():
    load_dotenv()
    if len(sys.argv) < 2:
        raise SystemExit('Uso: python -m agente "tu pregunta"')
    agente = AgenteGemini()
    texto, llamadas = agente.responder(" ".join(sys.argv[1:]))
    print(f"  [modelo] {getattr(agente, 'modelo_usado', '?')}")
    for llamada in llamadas:
        print(f"  [herramienta] {llamada['herramienta']} {llamada['argumentos']}")
    print("\n" + texto)


if __name__ == "__main__":
    main()
