#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Excel Mapper
────────────
Lee un PDF de preguntas y otro de respuestas + aclaraciones y genera OUTPUT.xlsx
con las 18 columnas de la plantilla, manteniendo la literalidad de todos los textos.

Ejemplo de uso
--------------
python excel_mapper.py --preguntas "Test nº2 T11.pdf" \
                       --respuestas "Test nº2 T11_Tabla.pdf" \
                       --tema 11
"""

import argparse
import re
from pathlib import Path
import os
from dotenv import load_dotenv
from openai import OpenAI
import json

import fitz  # PyMuPDF
import pandas as pd

# Cargar la clave de OpenAI
load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=openai_api_key)

# =========================
# 1) utilidades
# =========================
def extraer_texto(ruta_pdf: Path) -> str:
    """Devuelve todo el texto del PDF con saltos de línea preservados."""
    doc = fitz.open(ruta_pdf)
    return "\n".join(p.get_text(sort=True) for p in doc)  # sort=True → orden natural

def normalizar_saltos(texto: str) -> str:
    """Unifica saltos de línea \r\n / \r / \n en solo \n."""
    return texto.replace("\r\n", "\n").replace("\r", "\n")

# =========================
# 2) parsing de preguntas
# =========================
def obtener_preguntas(texto_preguntas: str):
    """
    Devuelve lista de tuplas:
      (nº, enunciado, A, B, C, D)
    Literalidad absoluta, tolerando saltos de línea en enunciado y opciones.
    """
    lineas = [l.rstrip() for l in texto_preguntas.splitlines()]
    preguntas = []
    i = 0
    while i < len(lineas):
        # Buscar inicio de pregunta: número punto espacio
        if lineas[i].strip().startswith(tuple(str(n)+'.' for n in range(1, 101))):
            num_match = re.match(r'^(\d{1,3})\.\s*(.*)', lineas[i].strip())
            if not num_match:
                i += 1
                continue
            num = int(num_match.group(1))
            enunciado = num_match.group(2)
            i += 1
            # Acumular líneas de enunciado hasta encontrar 'a)'
            while i < len(lineas) and not re.match(r'^[aA]\)', lineas[i].strip()):
                if lineas[i].strip():  # Solo agregar líneas no vacías
                    enunciado += (' ' if enunciado else '') + lineas[i].strip()
                i += 1
            # Limpiar espacios extra del enunciado
            enunciado = re.sub(r'\s+', ' ', enunciado.strip())
            # Acumular opciones
            opciones = {}
            for letra in ['A', 'B', 'C', 'D']:
                opcion = ''
                if i < len(lineas) and re.match(rf'^{letra.lower()}\)', lineas[i].strip(), re.IGNORECASE):
                    op_match = re.match(rf'^{letra.lower()}\)\s*(.*)', lineas[i].strip(), re.IGNORECASE)
                    opcion = op_match.group(1) if op_match else ''
                    i += 1
                    while i < len(lineas):
                        # Si la siguiente línea es otra opción o una nueva pregunta, paramos
                        if any(re.match(rf'^{l.lower()}\)', lineas[i].strip(), re.IGNORECASE) for l in ['A','B','C','D'] if l != letra):
                            break
                        if re.match(r'^(\d{1,3})\.\s*', lineas[i].strip()):
                            break
                        if lineas[i].strip():  # Solo agregar líneas no vacías
                            opcion += ' ' + lineas[i].strip()
                        i += 1
                    # Limpiar espacios extra de la opción
                    opcion = re.sub(r'\s+', ' ', opcion.strip())
                opciones[letra] = opcion
            if all(k in opciones for k in ['A','B','C','D']):
                preguntas.append((num, enunciado, opciones['A'], opciones['B'], opciones['C'], opciones['D']))
        else:
            i += 1
    return preguntas

# =========================
# 3) parsing de respuestas
# =========================
def obtener_respuestas(texto_respuestas: str):
    """
    Devuelve dos diccionarios:
      respuestas[num]    -> 'A'-'F'
      aclaraciones[num]  -> texto completo
    """
    lineas = [l.rstrip() for l in texto_respuestas.splitlines()]
    respuestas, aclaraciones = {}, {}
    patron = re.compile(r'(\b(\d{1,2})\s+([A-F])\b)')
    bloques = []
    bloque = []
    for l in lineas:
        if patron.search(l):
            if bloque:
                bloques.append(bloque)
            bloque = [l]
        else:
            bloque.append(l)
    if bloque:
        bloques.append(bloque)
    for b in bloques:
        # Buscar número y letra
        m = patron.search(b[0])
        if m:
            n = int(m.group(2))
            letra = m.group(3)
            respuestas[n] = letra
            # La aclaración es todo el bloque menos la primera línea
            aclaraciones[n] = "\n".join(b[1:]).strip()
    return respuestas, aclaraciones

# =========================
# LLM para extraer todas las aclaraciones
# =========================

def extraer_todas_aclaraciones_llm(texto_pdf_respuestas, lista_preguntas):
    """Una sola llamada al LLM para extraer todas las aclaraciones en formato JSON."""
    numeros_preguntas = [str(p[0]) for p in lista_preguntas]
    
    # Prompt mejorado para capturar aclaraciones completas (antes + después del patrón)
    prompt = f"""
Extrae las aclaraciones del PDF de respuestas de examen. Devuelve SOLO un JSON válido:

{{"1": "aclaración pregunta 1", "2": "aclaración pregunta 2", ...}}

INSTRUCCIONES CRÍTICAS:
- Busca el patrón: "NÚMERO + ESPACIOS + LETRA" (ej: "1      D", "2      B")
- La aclaración de cada pregunta está DIVIDIDA en dos partes:
  * ANTES del patrón: texto que pertenece a esa pregunta
  * DESPUÉS del patrón: continuación del texto hasta la siguiente pregunta
- Combina AMBAS partes para formar la aclaración completa
- LIMPIA EL FORMATO: elimina espacios extra, tabulaciones y saltos de línea innecesarios
- Convierte múltiples espacios en uno solo
- Mantén solo los saltos de línea necesarios para la estructura del texto
- Copia literal el CONTENIDO pero con formato limpio
- Si no hay aclaración, usa ""
- Solo JSON, sin texto extra

EJEMPLO DEL PATRÓN REAL:
```
Art. 12 Ley 45/2015 "El acuerdo de incorporación...  ← PARTE 1 (antes)
     1      D                                        ← PATRÓN
se requiera para el cumplimiento...convenido."       ← PARTE 2 (después)
```
La aclaración completa = PARTE 1 + PARTE 2 (con formato limpio)

Preguntas a procesar: {', '.join(numeros_preguntas[:10])}...{', '.join(numeros_preguntas[-5:])}

PDF:
{texto_pdf_respuestas[:80000]}"""

    try:
        respuesta = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=16000,
            temperature=0.0,
        )
        
        contenido = respuesta.choices[0].message.content.strip()
        print(f"[LLM] Respuesta recibida: {len(contenido)} caracteres")
        
        # GUARDAR LA RESPUESTA DEL LLM PARA ANÁLISIS
        with open("respuesta_llm.txt", "w", encoding="utf-8") as f:
            f.write("=== PROMPT ENVIADO ===\n")
            f.write(prompt)
            f.write("\n\n=== RESPUESTA DEL LLM ===\n")
            f.write(contenido)
        print(f"[LLM] 💾 Respuesta guardada en respuesta_llm.txt")
        
        # Limpiar posibles caracteres extra antes/después del JSON
        if contenido.startswith('```'):
            contenido = contenido.split('```')[1]
        if contenido.startswith('json'):
            contenido = contenido[4:]
        contenido = contenido.strip()
        
        # Intentar parsear el JSON
        try:
            aclaraciones_json = json.loads(contenido)
            # Convertir claves a enteros
            resultado = {int(k): v for k, v in aclaraciones_json.items()}
            print(f"[LLM] ✅ Extraídas {len(resultado)} aclaraciones")
            return resultado
        except json.JSONDecodeError as e:
            print(f"[LLM] ❌ Error parseando JSON: {e}")
            print(f"[LLM] Contenido: {contenido[:500]}...")
            return {}
            
    except Exception as e:
        print(f"[LLM] ❌ Error: {e}")
        return {}

# =========================
# 4) construcción del Excel
# =========================
COLUMNAS = [
    "Id pregunta para imagen",
    "Enunciado pregunta",
    "Texto respuesta A",
    "Texto respuesta B",
    "Texto respuesta C",
    "Texto respuesta D",
    "Texto respuesta E",
    "Texto respuesta F",
    "Respuesta correcta",
    "Nº Tema",
    "Nombre Tema",
    "Nombre de subtema",
    "Nombre del apartado",
    "Etiqueta",
    "Tipo Tema (T o P)",
    "Aclaración respuesta",
    "Estado",
    "Contexto de aclaración",
]

def generar_excel(pregs, resps, aclas, tema_num, texto_pdf_respuestas):
    # Una sola llamada al LLM para todas las aclaraciones
    aclaraciones_llm = extraer_todas_aclaraciones_llm(texto_pdf_respuestas, pregs)
    
    filas = []
    for (num, enunciado, a, b, c, d) in pregs:
        aclaracion = aclaraciones_llm.get(num, "")
        if not aclaracion:  # Si está vacía, intentar con string
            aclaracion = aclaraciones_llm.get(str(num), "")
        
        filas.append({
            "Id pregunta para imagen": num,
            "Enunciado pregunta": enunciado,
            "Texto respuesta A": a,
            "Texto respuesta B": b,
            "Texto respuesta C": c,
            "Texto respuesta D": d,
            "Texto respuesta E": "",
            "Texto respuesta F": "",
            "Respuesta correcta": resps.get(num, ""),
            "Nº Tema": tema_num or "",
            "Nombre Tema": "",
            "Nombre de subtema": "",
            "Nombre del apartado": "",
            "Etiqueta": "",
            "Tipo Tema (T o P)": "",
            "Aclaración respuesta": aclaracion if aclaracion else None,
            "Estado": "Publicada",
            "Contexto de aclaración": "",
        })
    df = pd.DataFrame(filas, columns=COLUMNAS)
    df.to_excel("OUTPUT.xlsx", index=False, engine="openpyxl")
    print("✅ OUTPUT.xlsx generado con éxito.")

# =========================
# 5) CLI
# =========================
def main():
    parser = argparse.ArgumentParser(description="Genera OUTPUT.xlsx a partir de 2 PDFs.")
    parser.add_argument("--preguntas", required=True, help="Ruta al PDF de preguntas")
    parser.add_argument("--respuestas", required=True, help="Ruta al PDF de respuestas + aclaraciones")
    parser.add_argument("--tema", help="Número de Tema (opcional)")
    args = parser.parse_args()

    # 1) leer PDFs
    texto_p = normalizar_saltos(extraer_texto(Path(args.preguntas)))
    texto_r = normalizar_saltos(extraer_texto(Path(args.respuestas)))

    # DEBUG: mostrar las primeras 40 líneas del texto de respuestas extraído
    print("--- Primeras 40 líneas del PDF de respuestas extraído ---")
    for idx, l in enumerate(texto_r.splitlines()[:40]):
        print(f"{idx+1:02d}: {repr(l)}")
    print("----------------------------------------------------------")

    # 2) parsear
    preguntas = obtener_preguntas(texto_p)
    respuestas, aclaraciones = obtener_respuestas(texto_r)

    # DEBUG: mostrar los números de pregunta y respuestas detectados
    print("Números de pregunta extraídos:", [p[0] for p in preguntas])
    print("Números de respuesta extraídos:", list(respuestas.keys()))
    if respuestas:
        k = list(respuestas.keys())[0]
        print(f"Ejemplo respuesta: {k} -> {respuestas[k]}")
        print(f"Ejemplo aclaración: {k} -> {aclaraciones[k][:100]}...")

    # 3) construir Excel
    generar_excel(preguntas, respuestas, aclaraciones, args.tema, texto_r)

if __name__ == "__main__":
    main() 