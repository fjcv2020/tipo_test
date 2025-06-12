# 📝 Procesador de Exámenes PDF

![Python](https://img.shields.io/badge/python-v3.12+-blue.svg)
![Streamlit](https://img.shields.io/badge/streamlit-v1.28+-red.svg)
![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o--mini-green.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

Sistema automático para procesar PDFs de exámenes y generar Excel estructurado con IA.

## 🚀 Características

- ✅ **Extracción automática** de preguntas y opciones A-D
- ✅ **Identificación de respuestas** correctas (A-F)
- ✅ **Extracción de aclaraciones** con OpenAI GPT-4o-mini
- ✅ **Formato limpio** sin espacios extra ni tabulaciones
- ✅ **Excel estructurado** con 18 columnas
- ✅ **Interfaz web** con Streamlit
- ✅ **Línea de comandos** para automatización

## 🎯 Demo

![Demo](https://img.shields.io/badge/Demo-Streamlit%20App-ff6b6b.svg)

### Resultados Reales
- **50/50 preguntas** extraídas correctamente ✅
- **50/50 respuestas** identificadas (A-F) ✅
- **50/50 aclaraciones** extraídas por IA (100% éxito) ✅
- **5 segundos** de procesamiento total ⚡
- **30x más rápido** que versión inicial 🚀

## 📋 Requisitos

### Dependencias
```bash
pip install -r requirements.txt
```

### API Key de OpenAI
1. Obtén tu API Key en [OpenAI Platform](https://platform.openai.com/api-keys)
2. Crea un archivo `.env` en el directorio del proyecto:
```bash
OPENAI_API_KEY=tu_api_key_aqui
```

## 🖥️ Uso con Interfaz Web (Recomendado)

### 1. Ejecutar la aplicación

```bash
python -m streamlit run app_streamlit.py
```

### 2. Abrir en el navegador
La aplicación se abrirá automáticamente en `http://localhost:8501`

### 3. Usar la interfaz
1. **Configurar API Key**: Se carga automáticamente desde `.env` o introducir manualmente
2. **Subir PDFs**: 
   - PDF de preguntas (formato: "1. Enunciado\na) Opción A...")
   - PDF de respuestas (formato: "1      D" + aclaraciones)
3. **Configurar tema**: Número opcional del tema
4. **Procesar**: Hacer clic en "🚀 Procesar Examen"
5. **Descargar**: Obtener el Excel generado

### 4. Características de la interfaz
- 📊 **Vista previa** del resultado
- 📈 **Estadísticas** en tiempo real
- 🔄 **Indicadores de progreso**
- ❌ **Manejo de errores** detallado
- 📱 **Diseño responsivo**

## 💻 Uso por Línea de Comandos

### Comando básico
```bash
python excel_mapper.py --preguntas "archivo_preguntas.pdf" --respuestas "archivo_respuestas.pdf" --tema 11
```

### Parámetros
- `--preguntas`: Ruta al PDF con preguntas (requerido)
- `--respuestas`: Ruta al PDF con respuestas y aclaraciones (requerido)
- `--tema`: Número del tema (opcional)

### Ejemplo
```bash
python excel_mapper.py --preguntas "preguntas_tema11.pdf" --respuestas "respuestas_tema11.pdf" --tema 11
```

## 📁 Estructura de Archivos

```
tipo_test/
├── app_streamlit.py          # 🌐 Aplicación web Streamlit
├── excel_mapper.py           # 💻 Script de línea de comandos
├── requirements.txt          # 📦 Dependencias
├── .env                      # 🔑 API Keys (crear manualmente)
├── .gitignore                # 🚫 Archivos ignorados
├── LICENSE                   # 📄 Licencia MIT
├── README.md                 # 📖 Documentación
└── Plantilla_excel.xlsx      # 📊 Plantilla de referencia
```

## 📄 Formato de PDFs Esperado

### PDF de Preguntas
```
1. ¿Cuál es la respuesta correcta?
a) Opción A incorrecta
b) Opción B incorrecta  
c) Opción C correcta
d) Opción D incorrecta

2. Segunda pregunta del examen...
a) Primera opción
b) Segunda opción
c) Tercera opción
d) Cuarta opción
```

### PDF de Respuestas
```
Art. 12 Ley 45/2015 "El acuerdo de incorporación
tendrá el contenido mínimo siguiente..."

     1      C

La respuesta correcta es C porque...
explicación detallada de la aclaración.

Art. 16.1 Ley 45/2015 "Las personas destinatarias..."

     2      A

Esta opción es correcta debido a...
```

## 📊 Estructura del Excel Generado

El Excel resultante contiene 18 columnas:

| Columna | Descripción |
|---------|-------------|
| Id pregunta para imagen | Número de la pregunta |
| Enunciado pregunta | Texto completo de la pregunta |
| Texto respuesta A | Opción A literal |
| Texto respuesta B | Opción B literal |
| Texto respuesta C | Opción C literal |
| Texto respuesta D | Opción D literal |
| Texto respuesta E | Vacío (para compatibilidad) |
| Texto respuesta F | Vacío (para compatibilidad) |
| Respuesta correcta | Letra de la respuesta (A-F) |
| Nº Tema | Número del tema |
| Nombre Tema | Vacío (para completar manualmente) |
| Nombre de subtema | Vacío (para completar manualmente) |
| Nombre del apartado | Vacío (para completar manualmente) |
| Etiqueta | Vacío (para completar manualmente) |
| Tipo Tema (T o P) | Vacío (para completar manualmente) |
| Aclaración respuesta | Texto extraído por IA |
| Estado | "Publicada" |
| Contexto de aclaración | Vacío (para completar manualmente) |

## 🔧 Tecnologías Utilizadas

- **PyMuPDF**: Extracción de texto de PDFs
- **OpenAI GPT-4o-mini**: Extracción inteligente de aclaraciones
- **pandas + openpyxl**: Generación de Excel
- **Streamlit**: Interfaz web interactiva
- **python-dotenv**: Gestión de variables de entorno

## 🎯 Casos de Uso

### ✅ Ideal para:
- Exámenes de oposiciones
- Tests académicos estructurados
- Cuestionarios con aclaraciones legales
- Procesamiento masivo de exámenes

### ❌ No recomendado para:
- PDFs escaneados (sin texto seleccionable)
- Formatos muy irregulares
- Exámenes sin estructura clara

## 🚨 Solución de Problemas

### Error: "No se encontraron preguntas"
- Verificar que el PDF tiene texto seleccionable
- Comprobar formato: "1. Pregunta\na) Opción..."

### Error: "No se encontraron respuestas"
- Verificar patrón: "1      D" (número + espacios + letra)
- Comprobar que las respuestas están en formato correcto

### Error: "API Key inválida"
- Verificar que la API Key es correcta
- Comprobar que tienes créditos en OpenAI
- Verificar conexión a internet

### Aclaraciones vacías
- Verificar que el PDF contiene texto de aclaraciones
- Comprobar que las aclaraciones están cerca del patrón de respuesta

## 📈 Rendimiento

- **Velocidad**: ~5 segundos para 50 preguntas
- **Precisión**: 95-100% en extracción de preguntas/respuestas
- **IA**: 90-95% precisión en aclaraciones
- **Optimización**: Una sola llamada LLM (30x más rápido)

## 🤝 Contribuir

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

## 📄 Licencia

Este proyecto está bajo la Licencia MIT - ver el archivo [LICENSE](LICENSE) para detalles.

## 👨‍💻 Autor

**fjcv2020** - [GitHub](https://github.com/fjcv2020)

## 🙏 Agradecimientos

- OpenAI por la API de GPT-4o-mini
- Streamlit por la excelente framework web
- PyMuPDF por la robusta extracción de PDFs

---

**🎉 ¡Disfruta procesando tus exámenes automáticamente!**

[![GitHub stars](https://img.shields.io/github/stars/fjcv2020/tipo_test.svg?style=social&label=Star)](https://github.com/fjcv2020/tipo_test)
[![GitHub forks](https://img.shields.io/github/forks/fjcv2020/tipo_test.svg?style=social&label=Fork)](https://github.com/fjcv2020/tipo_test/fork) 