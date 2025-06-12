#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Aplicación Streamlit para Procesamiento de Exámenes PDF
======================================================
Interfaz web para subir PDFs de preguntas y respuestas y generar Excel automáticamente.

Uso:
    streamlit run app_streamlit.py
"""

import streamlit as st
import tempfile
import os
from pathlib import Path
import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI
import json
import re
import fitz  # PyMuPDF
import io

# Configuración de la página
st.set_page_config(
    page_title="Procesador de Exámenes PDF",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Cargar variables de entorno
load_dotenv()

# Funciones del procesamiento (copiadas de excel_mapper.py)
def extraer_texto(archivo_pdf) -> str:
    """Devuelve todo el texto del PDF con saltos de línea preservados."""
    doc = fitz.open(stream=archivo_pdf.read(), filetype="pdf")
    return "\n".join(p.get_text(sort=True) for p in doc)

def normalizar_saltos(texto: str) -> str:
    """Unifica saltos de línea y limpia espacios extra."""
    # Unificar saltos de línea
    texto = texto.replace("\r\n", "\n").replace("\r", "\n")
    
    # Dividir en líneas para procesar cada una
    lineas = texto.split('\n')
    lineas_limpias = []
    
    for linea in lineas:
        # Limpiar espacios al inicio y final
        linea_limpia = linea.strip()
        
        # Si la línea no está vacía, limpiar espacios internos excesivos
        if linea_limpia:
            # Reemplazar múltiples espacios por uno solo
            linea_limpia = re.sub(r'\s+', ' ', linea_limpia)
            lineas_limpias.append(linea_limpia)
        else:
            # Mantener líneas vacías para preservar estructura
            lineas_limpias.append('')
    
    # Reunir las líneas
    texto_limpio = '\n'.join(lineas_limpias)
    
    # Eliminar múltiples saltos de línea consecutivos (más de 2)
    texto_limpio = re.sub(r'\n{3,}', '\n\n', texto_limpio)
    
    return texto_limpio

def obtener_preguntas(texto_preguntas: str):
    """Extrae preguntas del PDF con formato limpio."""
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

def obtener_respuestas(texto_respuestas: str):
    """Extrae respuestas del PDF."""
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

def extraer_todas_aclaraciones_llm(texto_pdf_respuestas, lista_preguntas, api_key):
    """Extrae aclaraciones usando OpenAI."""
    client = OpenAI(api_key=api_key)
    numeros_preguntas = [str(p[0]) for p in lista_preguntas]
    
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
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=16000,
            temperature=0.0,
        )
        
        contenido = respuesta.choices[0].message.content.strip()
        
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
            return resultado
        except json.JSONDecodeError as e:
            st.error(f"Error parseando JSON del LLM: {e}")
            return {}
            
    except Exception as e:
        st.error(f"Error en llamada a OpenAI: {e}")
        return {}

def generar_excel(pregs, resps, aclas, tema_num, texto_pdf_respuestas, api_key):
    """Genera el Excel final."""
    # Columnas del Excel
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
    
    # Una sola llamada al LLM para todas las aclaraciones
    aclaraciones_llm = extraer_todas_aclaraciones_llm(texto_pdf_respuestas, pregs, api_key)
    
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
    return df

# Interfaz de Streamlit
def main():
    st.title("📝 Procesador de Exámenes PDF")
    st.markdown("---")
    
    # Sidebar con información
    with st.sidebar:
        st.header("ℹ️ Información")
        st.markdown("""
        **¿Qué hace esta aplicación?**
        
        1. 📄 Sube un PDF con preguntas de examen
        2. 📄 Sube un PDF con respuestas y aclaraciones  
        3. 🤖 Procesa automáticamente con IA
        4. 📊 Genera Excel con 18 columnas estructuradas
        5. ⬇️ Descarga el resultado
        
        **Formato esperado:**
        - **Preguntas**: "1. Enunciado\\na) Opción A\\nb) Opción B..."
        - **Respuestas**: "1      D" + aclaraciones
        """)
        
        st.markdown("---")
        st.markdown("**🔧 Configuración**")
    
    # Configuración de API Key
    st.header("🔑 Configuración de OpenAI")
    
    # Intentar cargar desde .env
    api_key_env = os.getenv("OPENAI_API_KEY")
    if api_key_env:
        st.success("✅ API Key cargada desde archivo .env")
        api_key = api_key_env
    else:
        st.warning("⚠️ No se encontró API Key en .env")
        api_key = st.text_input(
            "Introduce tu API Key de OpenAI:",
            type="password",
            help="Necesaria para extraer aclaraciones con IA"
        )
    
    if not api_key:
        st.error("❌ Se requiere una API Key de OpenAI para continuar")
        st.stop()
    
    st.markdown("---")
    
    # Subida de archivos
    st.header("📁 Subir Archivos PDF")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📄 PDF de Preguntas")
        archivo_preguntas = st.file_uploader(
            "Sube el PDF con las preguntas del examen",
            type=['pdf'],
            key="preguntas"
        )
        
        if archivo_preguntas:
            st.success(f"✅ {archivo_preguntas.name}")
    
    with col2:
        st.subheader("📄 PDF de Respuestas")
        archivo_respuestas = st.file_uploader(
            "Sube el PDF con respuestas y aclaraciones",
            type=['pdf'],
            key="respuestas"
        )
        
        if archivo_respuestas:
            st.success(f"✅ {archivo_respuestas.name}")
    
    # Configuración adicional
    st.header("⚙️ Configuración")
    tema_num = st.number_input(
        "Número de Tema (opcional):",
        min_value=1,
        max_value=100,
        value=None,
        help="Número del tema para incluir en el Excel"
    )
    
    # Botón de procesamiento
    if archivo_preguntas and archivo_respuestas:
        st.markdown("---")
        
        if st.button("🚀 Procesar Examen", type="primary", use_container_width=True):
            with st.spinner("🔄 Procesando PDFs..."):
                try:
                    # Extraer texto de los PDFs
                    st.info("📖 Extrayendo texto de los PDFs...")
                    texto_preguntas = normalizar_saltos(extraer_texto(archivo_preguntas))
                    texto_respuestas = normalizar_saltos(extraer_texto(archivo_respuestas))
                    
                    # Parsear preguntas y respuestas
                    st.info("🔍 Analizando preguntas y respuestas...")
                    preguntas = obtener_preguntas(texto_preguntas)
                    respuestas, aclaraciones = obtener_respuestas(texto_respuestas)
                    
                    # Mostrar estadísticas
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("📝 Preguntas", len(preguntas))
                    with col2:
                        st.metric("✅ Respuestas", len(respuestas))
                    with col3:
                        st.metric("📋 Aclaraciones", len(aclaraciones))
                    
                    if len(preguntas) == 0:
                        st.error("❌ No se encontraron preguntas en el PDF")
                        st.stop()
                    
                    if len(respuestas) == 0:
                        st.error("❌ No se encontraron respuestas en el PDF")
                        st.stop()
                    
                    # Generar Excel
                    st.info("🤖 Extrayendo aclaraciones con IA...")
                    df_resultado = generar_excel(
                        preguntas, respuestas, aclaraciones, 
                        tema_num, texto_respuestas, api_key
                    )
                    
                    st.success("✅ ¡Procesamiento completado!")
                    
                    # Mostrar preview
                    st.header("👀 Vista Previa del Resultado")
                    st.dataframe(df_resultado.head(), use_container_width=True)
                    
                    # Preparar descarga
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        df_resultado.to_excel(writer, index=False, sheet_name='Examen')
                    
                    excel_data = output.getvalue()
                    
                    # Botón de descarga
                    st.download_button(
                        label="⬇️ Descargar Excel",
                        data=excel_data,
                        file_name=f"examen_procesado_tema_{tema_num or 'X'}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        type="primary",
                        use_container_width=True
                    )
                    
                    # Estadísticas finales
                    st.header("📊 Estadísticas Finales")
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("📝 Total Preguntas", len(df_resultado))
                    with col2:
                        aclaraciones_llm = len([x for x in df_resultado['Aclaración respuesta'] if pd.notna(x) and x != ""])
                        st.metric("🤖 Aclaraciones IA", aclaraciones_llm)
                    with col3:
                        porcentaje = (aclaraciones_llm / len(df_resultado)) * 100 if len(df_resultado) > 0 else 0
                        st.metric("📈 Éxito IA", f"{porcentaje:.1f}%")
                    with col4:
                        st.metric("📊 Columnas", len(df_resultado.columns))
                
                except Exception as e:
                    st.error(f"❌ Error durante el procesamiento: {str(e)}")
                    st.exception(e)
    
    else:
        st.info("👆 Sube ambos archivos PDF para comenzar el procesamiento")

if __name__ == "__main__":
    main() 