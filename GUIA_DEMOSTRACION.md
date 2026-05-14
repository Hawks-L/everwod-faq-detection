# Guía de Demostración — Proyecto Everwod FAQ Detection

**Objetivo:** mostrar paso a paso cómo arrancar, ejecutar y validar el sistema de detección automática de patrones conversacionales.

---

## Archivos y carpetas necesarios

```
Proyecto-Integrador/
│
├── .env                        ← credenciales DB + parámetros pipeline
├── requirements.txt            ← dependencias Python
│
├── pipeline/                   ← núcleo del sistema (NO tocar)
│   ├── config.py
│   ├── db.py
│   ├── extractor.py
│   ├── embedder.py
│   ├── clusterer.py
│   ├── generator.py
│   ├── orchestrator.py
│   └── scheduler.py
│
├── api/
│   └── main.py                 ← API REST de validación humana
│
├── run_pipeline.py             ← ejecución manual del pipeline
├── run_scheduler.py            ← job periódico (cada 24 h)
├── run_api.py                  ← servidor FastAPI
├── evaluate.py                 ← evaluación experimental
├── export_docx.py              ← genera el .docx desde el .md
│
├── documento_tecnico.md        ← documento técnico (fuente)
└── documento_tecnico.docx      ← documento técnico (Word, entregable)
```

Archivos de datos (ya presentes, no se distribuyen):
- `pgdump_production_08-04-2026-22-02-09.sql` — dump de producción obfuscado
- `pgdump_clean.sql` — dump limpio (sin línea `\restrict`)
- `embeddings_cache.pkl` — caché de embeddings generados

---

## Requisitos previos (verificar antes de demostrar)

| Requisito | Cómo verificar |
|-----------|---------------|
| Python 3.10+ | `python --version` |
| Dependencias instaladas | `pip install -r requirements.txt` |
| Docker corriendo | `docker ps` |
| Contenedor PostgreSQL activo | `docker ps \| findstr postgres` |
| Ollama corriendo | `ollama list` |
| Modelo de embeddings disponible | `ollama list` → ver `nomic-embed-text` |
| Modelo LLM disponible | `ollama list` → ver `llama3.2:3b` |

---

## Paso 1 — Arrancar los servicios base

### 1a. Levantar PostgreSQL en Docker

```powershell
# Verificar que el contenedor ya existe y arrancarlo
docker start everwod-postgres

# Si no existe, crearlo (solo la primera vez):
docker run -d --name everwod-postgres `
  -e POSTGRES_USER=everwod `
  -e POSTGRES_PASSWORD=everwod123 `
  -e POSTGRES_DB=everwod_production `
  -p 5432:5432 postgres:15
```

Espera ~5 segundos y verifica conexión:

```powershell
docker exec everwod-postgres psql -U everwod -d everwod_production -c "\dt" | Select-Object -First 10
```

Debes ver tablas como `agent_chats`, `chat_messages`, `agent_faqs`, etc.

### 1b. Arrancar Ollama

```powershell
# Normalmente ya está corriendo como servicio; verificar:
ollama list

# Si no está corriendo, iniciarlo manualmente:
& "C:\Users\Hawks\AppData\Local\Programs\Ollama\ollama.exe" serve
```

---

## Paso 2 — Ejecutar el pipeline manualmente

Este es el **paso central** de la demostración.

```powershell
# Con ventana de 90 días (recomendado para demostración):
python run_pipeline.py --days 90

# Con ventana de 30 días (más rápido, menos datos):
python run_pipeline.py --days 30

# Solo para un workspace específico:
python run_pipeline.py --days 90 --workspace <id>
```

**Qué ocurre internamente (5 etapas):**

1. **Preparar DB** — crea la tabla `faq_suggestions` si no existe
2. **Extraer mensajes** — consulta `chat_messages` filtrando saludos, listas de contactos y textos menores a 15 caracteres
3. **Generar embeddings** — llama a `nomic-embed-text` vía Ollama (768 dims); usa caché en `embeddings_cache.pkl`
4. **Clustering DBSCAN** — agrupa por similitud coseno (eps=0.25, min_samples=3); descarta clusters de una sola conversación
5. **Generar FAQs** — `llama3.2:3b` redacta pregunta + respuesta por cluster; deduplica semánticamente

**Salida esperada:**
```
[1/5] Preparando base de datos...
[2/5] Extrayendo mensajes de usuarios...
  Mensajes extraídos: 5136
[3/5] Generando embeddings semánticos...
  Embeddings nuevos: 461 | Desde caché: 4675
[4/5] Aplicando clustering DBSCAN...
  Clusters encontrados: 10
[5/5] Generando sugerencias de FAQs con LLM...
  FAQs duplicadas eliminadas: 1
  Pipeline completado: 9 FAQs guardadas en faq_suggestions.
```

> La primera ejecución tarda ~25-30 min (generación de embeddings).
> Ejecuciones siguientes tardan ~2-3 min gracias al caché.

---

## Paso 3 — Consultar las FAQs generadas

### Opción A: directo en la base de datos

```powershell
docker exec everwod-postgres psql -U everwod -d everwod_production -c `
  "SELECT id, workspace_id, question, status, message_count FROM faq_suggestions ORDER BY message_count DESC;"
```

### Opción B: vía API REST (recomendado para demostración visual)

Arranca el servidor en una terminal aparte:

```powershell
python run_api.py
```

Luego abre en el navegador:

| URL | Qué muestra |
|-----|-------------|
| `http://localhost:8000/docs` | Swagger UI — todos los endpoints interactivos |
| `http://localhost:8000/suggestions` | Lista de FAQs sugeridas (JSON) |
| `http://localhost:8000/suggestions/stats` | Totales por estado (pending/approved/rejected) |
| `http://localhost:8000/health` | Estado de la API |

---

## Paso 4 — Validar FAQs (flujo humano)

Demostrar el flujo de aprobación/rechazo desde Swagger o con curl:

```powershell
# Aprobar una FAQ (reemplazar <uuid> con el id real)
Invoke-RestMethod -Method POST `
  -Uri "http://localhost:8000/suggestions/<uuid>/approve" `
  -ContentType "application/json" `
  -Body '{"reviewed_by": "demo_user"}'

# Rechazar una FAQ
Invoke-RestMethod -Method POST `
  -Uri "http://localhost:8000/suggestions/<uuid>/reject" `
  -ContentType "application/json" `
  -Body '{"reviewed_by": "demo_user"}'
```

Luego verificar que el estado cambió:

```powershell
Invoke-RestMethod "http://localhost:8000/suggestions/stats"
```

---

## Paso 5 — Demostrar el Scheduler (ejecución periódica)

```powershell
python run_scheduler.py
```

**Salida esperada:**
```
=======================================================
  SCHEDULER: Pipeline de Detección de FAQs
=======================================================
  Intervalo : cada 24 hora(s)
  Workspace : todos
  Ventana   : 90 días
  Zona horaria: America/Bogota
  Primera ejecución: inmediata

Presiona Ctrl+C para detener.
```

El scheduler ejecuta el pipeline inmediatamente al arrancar y luego cada 24 horas de forma autónoma. Presiona **Ctrl+C** para detenerlo.

---

## Paso 6 — Ejecutar la evaluación experimental

```powershell
python evaluate.py
```

Produce 4 secciones de métricas:

| Sección | Qué mide |
|---------|----------|
| 1. Extracción | Cobertura: mensajes válidos vs. brutos |
| 2. Clustering | Silhouette Score, Davies-Bouldin, distribución de clusters |
| 3. FAQs | Precisión: aprobadas / revisadas |
| 4. Ambigüedad | Diversidad textual, cobertura de conversaciones |

**Resultados obtenidos en la ejecución real (90 días):**

```
Mensajes brutos:               9,294
Mensajes normalizados:         5,136  (55.3% cobertura)
Clusters válidos:              10
Tasa de agrupamiento:          95.5%
Silhouette Score:              0.0596
Davies-Bouldin Index:          1.3724
FAQs generadas:                20 (→ 9 tras deduplicación)
Precisión validación humana:   50% (1/2 revisadas)
Conversaciones cubiertas:      2,220
Diversidad textual:            69.9%
```

---

## Paso 7 — Revisar el documento técnico

El documento formal está en dos formatos:

```powershell
# Abrir el Word (entregable académico)
Start-Process "documento_tecnico.docx"

# Ver el Markdown fuente
notepad documento_tecnico.md
```

Para regenerar el .docx después de editar el .md:

```powershell
python export_docx.py
```

---

## Flujo completo resumido

```
[Terminal 1]  docker start everwod-postgres
[Terminal 1]  python run_pipeline.py --days 90     ← ~2 min (con caché)
[Terminal 2]  python run_api.py                    ← servidor en :8000
[Navegador]   http://localhost:8000/docs           ← aprobar/rechazar FAQs
[Terminal 3]  python evaluate.py                   ← métricas experimentales
[Opcional]    python run_scheduler.py              ← demo de automatización
```

---

## Solución de problemas comunes

| Síntoma | Causa probable | Solución |
|---------|---------------|----------|
| `Connection refused` al conectar DB | Docker no está corriendo | `docker start everwod-postgres` |
| `Error 500` en Ollama | Modelo no descargado | `ollama pull nomic-embed-text` y `ollama pull llama3.2:3b` |
| Pipeline genera 0 clusters | Muy pocos mensajes o eps muy bajo | Aumentar `--days` o ajustar `DBSCAN_EPS=0.30` en `.env` |
| FAQs en inglés | LLM ignora instrucción de idioma | Verificar que el modelo `llama3.2:3b` esté completo con `ollama show llama3.2:3b` |
| `ModuleNotFoundError` | Dependencias no instaladas | `pip install -r requirements.txt` |
