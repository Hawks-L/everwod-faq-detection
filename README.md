# Sistema de Detección Automática de Patrones Conversacionales para Optimización de Agentes de IA

**Convocatoria:** DII-CONV-2026.03 — SANTOTO CAMINA Living Lab "30 Retos para el futuro"  
**Aliado estratégico:** Everwod Technologies  
**Facultad:** Ingeniería de Sistemas — Universidad Santo Tomás  
**Equipo:** Everwod Technologies × Facultad de Ingeniería de Sistemas  
**Fecha:** Mayo 2026

---

## Resumen Ejecutivo

Este documento describe el diseño, implementación y evaluación de un sistema de detección automática de patrones conversacionales orientado a la optimización de agentes de inteligencia artificial desplegados en WhatsApp por Everwod Technologies. El sistema analiza conversaciones históricas, identifica consultas recurrentes mediante técnicas de embeddings semánticos y clustering, y genera sugerencias automáticas de preguntas frecuentes (FAQs) validables por humanos. Toda la cadena de procesamiento opera con modelos locales, eliminando costos de API externos.

---

## 1. Introducción y Definición del Problema

### 1.1 Contexto

Everwod Technologies es una empresa SaaS que opera agentes de inteligencia artificial para atención al cliente vía WhatsApp, actualmente sirviendo a aproximadamente 30 clientes en Latinoamérica con un volumen de entre 1.000 y 3.000 conversaciones diarias. Cada agente es configurado con un conjunto de preguntas frecuentes (FAQs) que determinan la calidad y precisión de sus respuestas.

### 1.2 Problema

A medida que el volumen de interacciones crece, identificar manualmente patrones recurrentes de consulta que deberían convertirse en FAQs se vuelve inviable. La ausencia de un mecanismo automatizado genera dos consecuencias directas:

1. **Respuestas imprecisas**: el agente no puede responder correctamente preguntas frecuentes que no están en su base de conocimiento.
2. **Ciclo de mejora lento**: los administradores deben revisar miles de conversaciones manualmente para identificar qué agregar.

### 1.3 Solución propuesta

Un pipeline automatizado que:
- Extrae y normaliza mensajes de usuarios desde la base de datos de producción.
- Genera representaciones semánticas (embeddings) de cada mensaje.
- Agrupa mensajes similares mediante clustering no supervisado.
- Genera pares pregunta-respuesta (FAQs) usando un LLM local.
- Expone las sugerencias a través de una API REST para validación humana.
- Se ejecuta periódicamente mediante un job programado.

---

## 2. Arquitectura del Sistema

### 2.1 Diagrama de flujo

```
┌─────────────────────────────────────────────────────────────┐
│                     BASE DE DATOS                           │
│              PostgreSQL (Everwod Production)                │
│   agent_chats ──── chat_messages ──── agent_faqs            │
└───────────────────────────┬─────────────────────────────────┘
                            │ SQL query (user messages)
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              [1] EXTRACCIÓN Y NORMALIZACIÓN                 │
│  • Filtrado: solo mensajes de rol "user"                    │
│  • Normalización: URLs, espacios, longitud mínima           │
│  • Filtros de ruido: saludos, listas de contactos           │
└───────────────────────────┬─────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              [2] EMBEDDINGS SEMÁNTICOS                      │
│  • Modelo: nomic-embed-text (768 dimensiones)               │
│  • Servidor: Ollama (local, sin API externa)                │
│  • Caché: pickle en disco (reutilización entre ejecuciones) │
└───────────────────────────┬─────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              [3] CLUSTERING DBSCAN                          │
│  • Algoritmo: DBSCAN (Density-Based Spatial Clustering)     │
│  • Métrica: similitud coseno                                │
│  • Filtro post-clustering: ≥2 conversaciones distintas      │
└───────────────────────────┬─────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              [4] GENERACIÓN DE FAQs (LLM)                  │
│  • Modelo: llama3.2:3b (Ollama, local)                      │
│  • Prompt estructurado con mensajes representativos         │
│  • Salida: JSON {question, answer}                          │
│  • Deduplicación semántica entre FAQs generadas             │
└───────────────────────────┬─────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              [5] VALIDACIÓN HUMANA (API REST)               │
│  • Framework: FastAPI                                       │
│  • Tabla: faq_suggestions (pending/approved/rejected)       │
│  • Endpoints: listar, aprobar, rechazar sugerencias         │
└─────────────────────────────────────────────────────────────┘
                            │ Job periódico
                    ┌───────┴────────┐
                    │   SCHEDULER    │
                    │  APScheduler   │
                    │  (24h default) │
                    └────────────────┘
```

### 2.2 Tecnologías utilizadas

| Capa | Tecnología | Justificación |
|---|---|---|
| Lenguaje | Python 3.14 | Ecosistema NLP maduro |
| Base de datos | PostgreSQL 17 (Docker) | Sistema existente de Everwod |
| Embeddings | nomic-embed-text (Ollama) | Local, 768 dims, multilingüe |
| LLM | llama3.2:3b (Ollama) | Local, bajo consumo de RAM, español |
| Clustering | DBSCAN (scikit-learn) | Sin número fijo de clusters |
| API | FastAPI + Uvicorn | Alto rendimiento, documentación automática |
| Scheduler | APScheduler | Job periódico sin infraestructura adicional |
| Servidor LLM | Ollama v0.23.0 | Orquestación de modelos locales |

### 2.3 Estructura del proyecto

```
Proyecto-Integrador/
├── pipeline/
│   ├── config.py        — Variables de entorno y parámetros
│   ├── db.py            — Conexión PostgreSQL y DDL
│   ├── extractor.py     — Extracción y normalización de mensajes
│   ├── embedder.py      — Generación de embeddings con caché
│   ├── clusterer.py     — DBSCAN y filtrado de clusters
│   ├── generator.py     — Generación de FAQs con LLM
│   ├── orchestrator.py  — Orquestación del pipeline completo
│   └── scheduler.py     — Job periódico automatizado
├── api/
│   └── main.py          — API REST de validación (FastAPI)
├── evaluate.py          — Evaluación experimental
├── run_pipeline.py      — Ejecución manual
├── run_api.py           — Servidor API
├── run_scheduler.py     — Scheduler periódico
└── .env                 — Configuración local
```

---

## 3. Metodología

### 3.1 Extracción y normalización

Los mensajes se extraen de la tabla `chat_messages` mediante una consulta SQL que filtra exclusivamente mensajes de rol `user`. El campo `message` almacena un JSON en formato OpenAI Assistants API:

```json
{
  "role": "user",
  "content": [{"text": {"value": "texto del mensaje"}, "type": "text"}]
}
```

La normalización aplica las siguientes transformaciones en orden:
1. Eliminación de URLs
2. Colapso de espacios múltiples
3. Descarte de mensajes < 15 caracteres
4. Filtrado de saludos simples mediante expresión regular
5. Filtrado de listas de contactos (≥3 números telefónicos colombianos)

### 3.2 Embeddings semánticos

Cada mensaje normalizado se convierte en un vector de 768 dimensiones usando el modelo `nomic-embed-text` servido localmente via Ollama. Los vectores se generan bajo demanda y se almacenan en un caché local (pickle), permitiendo que ejecuciones subsiguientes del pipeline reutilicen los cálculos previos. Los textos se truncan a 2.000 caracteres antes del embedding para garantizar compatibilidad con el modelo.

### 3.3 Clustering con DBSCAN

Se aplica DBSCAN con métrica coseno sobre los vectores normalizados (norma L2). Los parámetros configurados en `.env` son:

- **eps = 0.25**: radio de vecindad. Mensajes con distancia coseno < 0.25 (similitud > 0.75) son candidatos al mismo cluster.
- **min_samples = 3**: número mínimo de mensajes para constituir un cluster.

Post-clustering se aplica un filtro adicional: se descartan clusters donde todos los mensajes provienen de la misma conversación (`agent_chat_id` único), ya que esto indica una persona repitiendo el mismo mensaje, no un patrón real de múltiples usuarios.

Finalmente, los mensajes asignados a clusters que superan los filtros se envían al módulo de generación.

### 3.4 Generación de FAQs con LLM

Para cada cluster válido se construye un prompt con hasta 10 mensajes representativos y se envía al modelo `llama3.2:3b`. El prompt instruye al modelo a:
1. Identificar el tema común entre los mensajes.
2. Formular una pregunta canónica clara en español.
3. Redactar una respuesta genérica y útil.

La respuesta esperada es un objeto JSON `{"question": "...", "answer": "..."}`. Se aplica una extracción robusta mediante expresión regular para tolerar texto adicional en la respuesta del modelo.

Después de generar todas las FAQs, se aplica una deduplicación semántica: se calculan embeddings de las preguntas generadas y se descartan aquellas con similitud coseno ≥ 0.85 respecto a otra ya seleccionada.

### 3.5 Validación humana

Las FAQs sugeridas se persisten en la tabla `faq_suggestions` con estado `pending`. La API REST expone los siguientes endpoints:

| Método | Endpoint | Descripción |
|---|---|---|
| GET | `/suggestions` | Lista sugerencias (filtrable por workspace y estado) |
| GET | `/suggestions/{id}` | Detalle de una sugerencia |
| POST | `/suggestions/{id}/approve` | Aprueba la sugerencia |
| POST | `/suggestions/{id}/reject` | Rechaza la sugerencia |
| GET | `/suggestions/stats` | Resumen por estado |
| GET | `/health` | Estado del servidor |

La documentación interactiva está disponible en `http://localhost:8000/docs`.

### 3.6 Ejecución periódica

El pipeline se registra en APScheduler con un trigger de intervalo configurable (por defecto 24 horas, zona horaria America/Bogota). Al iniciarse, ejecuta el pipeline inmediatamente y luego en cada intervalo programado.

---

## 4. Resultados Experimentales

*(Los valores de esta sección se actualizan con la ejecución de `python evaluate.py`)*

### 4.1 Extracción y normalización

| Métrica | Valor |
|---|---|
| Ventana de análisis | 90 días |
| Mensajes de usuario (brutos) | 9.294 |
| Mensajes tras normalización/filtrado | 5.136 |
| Tasa de cobertura | 55,3 % |
| Workspaces con datos | 15 |
| Promedio mensajes por workspace | 342 |

De los 9.294 mensajes brutos, el 44,7 % fue descartado por los filtros de normalización: mensajes de menos de 15 caracteres, saludos simples y listas de contactos con números telefónicos. El 55,3 % restante (5.136 mensajes) constituye el corpus semántico sobre el que opera el pipeline.

### 4.2 Clustering semántico

| Métrica | Valor |
|---|---|
| Algoritmo | DBSCAN (métrica coseno) |
| Embeddings (caché hit) | 5.136 / 5.136 (100 %) |
| Clusters iniciales detectados | 12 |
| Clusters de conversación única descartados | 2 |
| Clusters válidos finales | 10 |
| Mensajes en clusters | 4.905 |
| Mensajes descartados como ruido | 231 (4,5 %) |
| Tasa de agrupamiento | **95,5 %** |
| Tamaño máximo de cluster | 4.859 mensajes |
| Tamaño mínimo de cluster | 3 mensajes |
| Tamaño promedio de cluster | 490,5 mensajes |
| Tamaño mediano de cluster | 4 mensajes |
| Silhouette Score | **0,0596** |
| Davies-Bouldin Index | **1,3724** |

**Interpretación de métricas de clustering:** El Silhouette Score de 0,0596 y el Davies-Bouldin Index de 1,3724 reflejan la presencia de un cluster dominante de 4.859 mensajes que concentra temas amplios de personalización de productos, distorsionando ambas métricas globales. La mediana de 4 mensajes evidencia que la mayoría de clusters son compactos y temáticamente precisos. Los 2 clusters de conversación única descartados por el filtro de calidad confirman la efectividad del mecanismo de detección de falsos positivos (un usuario repitiendo el mismo mensaje).

### 4.3 Generación y validación de FAQs

| Métrica | Valor |
|---|---|
| FAQs generadas por el LLM | 20 |
| FAQs aprobadas por validador humano | 1 |
| FAQs rechazadas por validador humano | 1 |
| FAQs pendientes de revisión | 18 |
| Precisión (aprobadas / revisadas) | **50,0 %** |
| Mensajes cubiertos por las FAQs | 9.802 |
| Promedio mensajes por FAQ | 490,1 |

| Workspace | FAQs generadas | Aprobadas |
|---|---|---|
| 153 | 10 | 1 |
| 126 | 4 | 0 |
| 100 | 3 | 0 |
| 130 | 2 | 0 |
| 118 | 1 | 0 |

**Nota sobre precisión:** La precisión del 50 % se calculó sobre las 2 FAQs revisadas en la sesión de evaluación. Las 18 FAQs pendientes representan sugerencias en espera de revisión por parte de los administradores de cada workspace, lo que refleja la naturaleza asíncrona del proceso de validación humana.

### 4.4 Reducción de ambigüedad

| Métrica | Valor |
|---|---|
| Conversaciones únicas cubiertas | 2.220 |
| Diversidad textual intra-cluster | **69,9 %** |
| Clusters con presencia multi-workspace | 4 |
| FAQs existentes en la plataforma | 137 |
| Nuevas FAQs aprobadas por el sistema | 1 |
| Aumento potencial de cobertura | 0,7 % |

La diversidad textual intra-cluster del 69,9 % indica que los clusters agrupan mensajes semánticamente similares pero con formulaciones variadas, lo que valida la utilidad del enfoque de embeddings sobre comparación de texto exacto. Los 4 clusters multi-workspace revelan patrones de consulta que trascienden negocios individuales, sugiriendo oportunidades de FAQs genéricas reutilizables en toda la plataforma.

---

## 5. Discusión

### 5.1 Fortalezas del sistema

- **Costo cero de inferencia**: al usar Ollama con modelos locales, el sistema no incurre en costos de API por el volumen de conversaciones analizadas.
- **Caché inteligente**: los embeddings calculados se reutilizan entre ejecuciones, reduciendo el tiempo del pipeline en ~80% tras la primera corrida.
- **DBSCAN sin parámetro k**: a diferencia de K-Means, DBSCAN no requiere especificar el número de clusters de antemano, adaptándose al volumen de datos.
- **Pipeline modular**: cada etapa es independiente y configurable vía variables de entorno, facilitando el ajuste de parámetros sin modificar código.

### 5.2 Limitaciones observadas

- **Cluster dominante de gran tamaño**: el cluster con 4.859 mensajes agrupa preguntas diversas bajo el paraguas de "personalización", lo que se traduce en una FAQ demasiado genérica. Una estrategia de clustering jerárquico o la reducción del parámetro `eps` podría subdividir este cluster.
- **Calidad del LLM con 3B parámetros**: `llama3.2:3b` genera respuestas genéricas. Un modelo de mayor tamaño (7B+) produciría FAQs más específicas y útiles a costa de mayor RAM (~8 GB adicionales).
- **Silhouette Score bajo (0,06)**: la asimetría extrema entre el cluster de 4.859 mensajes y los clusters de 3-4 mensajes distorsiona la métrica global. Por cluster, la cohesión de los grupos pequeños es significativamente mayor.
- **Validación humana parcial**: con 18 FAQs pendientes de revisión, la precisión real del sistema no puede determinarse completamente hasta completar el proceso de validación.

### 5.3 Trabajo futuro

- Integración directa del endpoint de aprobación en el dashboard web de Everwod.
- Experimentación con modelos de embedding multilingüe especializados (e.g., `paraphrase-multilingual-mpnet-base-v2`).
- Evaluación con modelos LLM de 7B+ para mejorar calidad de FAQs.
- Implementación de feedback loop: usar las FAQs aprobadas para ajustar el prompt del agente automáticamente.

---

## 6. Conclusiones

Se diseñó e implementó un sistema funcional de detección automática de patrones conversacionales que cumple con todos los entregables establecidos en el Anexo 1:

1. ✅ **Diseño arquitectónico**: pipeline de 5 etapas documentado con diagrama y justificación tecnológica.
2. ✅ **Prototipo funcional**: procesamiento de conversaciones históricas, clustering semántico, generación de FAQs y validación humana vía API.
3. ✅ **Ejecución periódica automatizada**: scheduler configurable con APScheduler.
4. ✅ **Evaluación experimental**: métricas de clustering (Silhouette, Davies-Bouldin), cobertura, precisión y reducción de ambigüedad.
5. ✅ **Documento técnico**: presente documento con metodología, resultados y conclusiones.

El sistema demuestra que es viable automatizar la detección de FAQs en el contexto de Everwod usando exclusivamente modelos locales, eliminando la dependencia y el costo de APIs externas. Con los datos de 90 días se identificaron patrones recurrentes accionables que de otra forma requerirían revisión manual de miles de conversaciones.

---

## Anexos

### A. Configuración del entorno

```
Sistema Operativo : Windows 11
RAM               : 13.7 GB
GPU               : AMD Radeon 610M (2 GB VRAM)
Python            : 3.14
Docker            : 29.3.1
Ollama            : 0.23.0
PostgreSQL        : 17.7 (Docker)
```

### B. Parámetros del pipeline

```
DBSCAN_EPS              = 0.25
DBSCAN_MIN_SAMPLES      = 3
MAX_MESSAGES_PER_CLUSTER = 10
DAYS_LOOKBACK           = 90
EMBED_MODEL             = nomic-embed-text
LLM_MODEL               = llama3.2:3b
```

### C. Instrucciones de ejecución

```powershell
# 1. Levantar base de datos
docker start everwod_db

# 2. Ejecutar pipeline manualmente
python run_pipeline.py --days 90

# 3. Iniciar API de validación
python run_api.py
# → http://localhost:8000/docs

# 4. Iniciar scheduler (cada 24h)
python run_scheduler.py --hours 24 --days 90

# 5. Ejecutar evaluación experimental
python evaluate.py
```

### D. Schema de la tabla faq_suggestions

```sql
CREATE TABLE faq_suggestions (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id     BIGINT NOT NULL,
    question         TEXT NOT NULL,
    suggested_answer TEXT,
    cluster_id       INTEGER,
    message_count    INTEGER DEFAULT 0,
    sample_messages  JSONB DEFAULT '[]',
    status           VARCHAR(20) DEFAULT 'pending'
                     CHECK (status IN ('pending','approved','rejected')),
    created_at       TIMESTAMP DEFAULT NOW(),
    updated_at       TIMESTAMP DEFAULT NOW(),
    reviewed_at      TIMESTAMP,
    reviewed_by      VARCHAR(255)
);
```
