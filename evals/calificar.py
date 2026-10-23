"""Califica una respuesta del agente contra el valor correcto. No usa IA: reglas fijas y verificables."""

import re

NUMERO = re.compile(r"-?\d[\d.,]*")
FRASES_SIN_DATO = ["no tengo", "no dispongo", "no cuento", "no puedo", "no está disponible",
                   "no esta disponible", "no tengo acceso", "solo tengo", "sólo tengo",
                   "no incluye", "no forma parte", "fuera de"]


def numeros_en(texto):
    """Extrae los números de un texto, aceptando formato chileno (1.234,56) y anglosajón (1,234.56)."""
    valores = set()
    for crudo in NUMERO.findall(texto):
        crudo = crudo.strip(".,")
        if not crudo or crudo == "-":
            continue
        candidatos = [
            crudo.replace(".", "").replace(",", "."),   # chileno: punto = miles, coma = decimal
            crudo.replace(",", ""),                      # anglosajón: coma = miles, punto = decimal
        ]
        for c in candidatos:
            try:
                valores.add(float(c))
            except ValueError:
                pass
    return valores


def cerca(valor, esperado):
    """Tolerancia: 1 % del valor (permite redondear 978,56 a 979) o 0,02 para cifras chicas."""
    margen = max(abs(esperado) * 0.01, 0.02)
    return abs(valor - esperado) <= margen or abs(abs(valor) - abs(esperado)) <= margen


def calificar(caso, texto, llamadas):
    """Devuelve (aprobado, motivo)."""
    if caso.get("fuera_de_alcance"):
        reconoce = any(f in texto.lower() for f in FRASES_SIN_DATO)
        return (reconoce, "reconoce que no tiene el dato" if reconoce else "no reconoció que no tiene el dato")

    if not llamadas:
        return False, "respondió sin usar herramientas (posible invención)"
    herramienta = caso.get("herramienta")
    if herramienta and herramienta not in [l["herramienta"] for l in llamadas]:
        return False, f"no usó {herramienta}"

    esperado = caso["esperado"]()
    if any(cerca(v, esperado) for v in numeros_en(texto)):
        return True, f"cifra correcta ({esperado})"
    return False, f"cifra incorrecta o ausente (esperado {esperado})"
