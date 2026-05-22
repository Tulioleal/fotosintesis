# Fotosíntesis AI — decisiones-tecnicas.spec.md

## Estado

Decisiones técnicas aprobadas para la especificación preliminar del proyecto.

---

## 1. Frontend

## Frontend state management

### Decisión

El frontend se implementará con:

- TypeScript
- React
- Next.js
- SCSS Modules
- TanStack Query
- Zustand

### TypeScript

TypeScript será obligatorio en el frontend para tipar componentes, hooks, DTOs, respuestas de API, formularios y estados de UI.

### TanStack Query

TanStack Query se usará para gestionar estado servidor:

- requests HTTP;
- cache;
- loading states;
- error states;
- retries;
- invalidación de queries;
- mutaciones;
- sincronización con el backend.

Ejemplos de datos gestionados por TanStack Query:

- plantas identificadas;
- fichas de planta;
- Mi Jardín;
- recordatorios;
- mediciones de luz;
- conversaciones;
- resultados del asistente;
- estados de adquisición incremental.

### Zustand

Zustand se usará para estado cliente y de interfaz:

- flujo actual de identificación;
- candidata seleccionada;
- estado temporal de cámara;
- modales;
- filtros locales;
- formularios en progreso;
- pasos de onboarding;
- preferencias visuales locales.

### Regla de separación

TanStack Query será la fuente de verdad para datos remotos.
Zustand no debe duplicar datos persistidos en backend salvo como estado temporal de UI.

### No usar

```text
Tailwind
```

### Justificación

La aplicación parte de un UI kit y una identidad visual existente. SCSS Modules permite mantener estilos encapsulados por componente sin abandonar control fino sobre tokens, variables, mixins, spacing, estados visuales y composición.

### Estructura sugerida

```text
frontend/
  src/
    app/
    components/
      PlantCard/
        PlantCard.tsx
        PlantCard.module.scss
      BottomNavigation/
        BottomNavigation.tsx
        BottomNavigation.module.scss
    styles/
      _tokens.scss
      _mixins.scss
      _typography.scss
      globals.scss
```

### Reglas

- Los estilos de componentes deben vivir en archivos `.module.scss`.
- Los tokens globales deben concentrarse en `styles/_tokens.scss`.
- La UI debe conservar la identidad de Fotosíntesis.
- El UI kit funciona como guía flexible, no como contrato rígido.
- Deben existir estados de loading, error, disabled, empty state y success.

---

## 2. Backend API

### Decisión

Usar:

```text
FastAPI + Uvicorn
```

### Responsabilidades

- Exponer endpoints documentados.
- Servir inferencia generativa.
- Orquestar agente y herramientas.
- Integrar RAG.
- Gestionar usuarios, plantas, jardín y recordatorios.
- Exponer health check.
- Exponer métricas básicas.
- Registrar eventos de observabilidad.

### Endpoints mínimos

```text
GET  /health
GET  /metrics
POST /chat
POST /plants/identify
GET  /plants/{id}
POST /garden
GET  /garden
POST /reminders
GET  /reminders
POST /light-measurements
POST /evaluation/run
```

---

## 3. MaaS agnóstico al servicio

### Decisión

El sistema debe ser agnóstico al proveedor de modelos.

No se debe acoplar la lógica de dominio a OpenAI, Anthropic, Gemini, Vertex AI, Ollama u otro proveedor específico.

### Interfaz conceptual

```python
class ModelProvider:
    async def generate_text(self, prompt, **kwargs): ...
    async def generate_json(self, prompt, schema, **kwargs): ...
    async def analyze_image(self, image, prompt, **kwargs): ...
    async def create_embeddings(self, texts, **kwargs): ...
    async def judge_response(self, payload, rubric, **kwargs): ...
```

### Implementaciones posibles

```text
OpenAIProvider
AnthropicProvider
GeminiProvider
VertexAIProvider
OllamaProvider
MockProvider
```

### Regla

El backend debe depender de interfaces propias, no de SDKs de proveedores en la lógica de negocio.

---

## 4. Orquestación de agente

### Decisión

Usar:

```text
LangGraph
```

### Justificación

El flujo del agente no es lineal. Tiene decisiones, herramientas, reintentos y estado. LangGraph se ajusta mejor que una chain simple para modelar flujos como:

```text
Pregunta del usuario
  ↓
Clasificar intención
  ↓
Consultar datos del usuario
  ↓
Consultar RAG
  ↓
¿Hay evidencia suficiente?
  ├─ Sí → generar respuesta
  └─ No → búsqueda web controlada
            ↓
          validar fuentes
            ↓
          persistir documento
            ↓
          crear embeddings
            ↓
          reintentar RAG
            ↓
          responder
```

### Nodos sugeridos

```text
classify_intent
load_user_context
retrieve_knowledge
evaluate_context_sufficiency
web_search_trusted_sources
extract_and_normalize
validate_sources
persist_knowledge
embed_knowledge
generate_answer
create_reminder
ask_clarification
handle_failure
```

### Tools del agente

```text
search_knowledge_base
search_trusted_web_sources
validate_taxonomy
ingest_knowledge_document
create_embeddings
identify_plant_from_image
get_user_garden
create_reminder
get_light_measurement
```

---

## 5. RAG e indexación

### Decisión

Usar:

```text
LlamaIndex
```

### Rol de LlamaIndex

LlamaIndex se usará para el subsistema de conocimiento:

```text
documentos adquiridos
  ↓
parsing / normalización
  ↓
chunking
  ↓
embeddings
  ↓
indexación en PostgreSQL + pgvector
  ↓
retrieval
  ↓
contexto para generación
```

### Responsabilidades

- Cargar documentos estructurados.
- Dividir documentos en chunks.
- Asociar metadata a chunks.
- Crear embeddings mediante el `ModelProvider`.
- Guardar embeddings en pgvector.
- Ejecutar retrieval por similitud semántica.
- Aplicar filtros por especie, tema, fuente, confianza y fecha.
- Devolver contexto al agente.

### Metadata obligatoria por chunk

```yaml
species_id:
scientific_name:
topic:
source_domain:
source_url:
confidence:
review_status:
retrieved_at:
created_at:
```

---

## 6. Base de datos

### Decisión

Usar:

```text
PostgreSQL
```

### Extensión vectorial

Usar:

```text
pgvector
```

### Justificación

Fotosíntesis tiene un dominio fuertemente relacional:

```text
Usuario
  ├─ Plantas guardadas
  │    ├─ Recordatorios
  │    ├─ Mediciones de luz
  │    └─ Historial
  ├─ Conversaciones
  └─ Preferencias regionales

Documento de conocimiento
  ├─ Especie
  ├─ Fuentes
  ├─ Chunks
  └─ Embeddings
```

PostgreSQL permite manejar relaciones, trazabilidad, filtros, integridad y búsqueda vectorial en una misma base.

### Uso en GCP

En GCP se podrá usar:

```text
Cloud SQL for PostgreSQL + pgvector
```

### Tablas sugeridas

```text
users
user_profiles
plants
plant_aliases
garden_plants
reminders
light_measurements
knowledge_documents
knowledge_sources
knowledge_chunks
conversations
conversation_messages
agent_tool_runs
evaluation_cases
evaluation_runs
```

---

## 7. Almacenamiento de imágenes

### Decisión

Usar un bucket para objetos.

En GCP:

```text
Cloud Storage Bucket
```

### Qué se guarda en bucket

```text
fotos subidas por usuarios
imágenes usadas para identificación
imágenes de diagnóstico
imágenes de referencia
archivos temporales de adquisición
```

### Qué se guarda en PostgreSQL

```text
image_id
user_id
plant_id
bucket_path
mime_type
size_bytes
created_at
expires_at
```

---

## 8. Identificación botánica

### Decisión

La identificación visual se implementará con un proveedor **MaaS multimodal agnóstico** como fuente principal.

La identificación no será tratada como una verdad definitiva. El sistema debe devolver **candidatas probables**, validar sus nombres científicos contra una fuente taxonómica y solicitar confirmación del usuario antes de generar una ficha, crear recordatorios o guardar la planta en Mi Jardín.

El núcleo generativo sigue siendo:

```text
asistente + RAG + adquisición incremental + generación de fichas + diagnóstico
```

La identificación visual es una herramienta auxiliar del agente.

### Interfaz

```python
class VisionPlantIdentificationProvider:
    async def identify_candidates(self, image, context=None) -> list[PlantCandidate]: ...
```

### Respuesta esperada

```json
{
  "candidates": [
    {
      "scientific_name": "Cotyledon tomentosa",
      "common_name": "Pata de oso",
      "confidence_label": "medium",
      "confidence_score": null,
      "visible_traits": [
        "hojas carnosas",
        "bordes con apariencia dentada",
        "crecimiento compacto"
      ],
      "provider": "maas_multimodal",
      "needs_user_confirmation": true
    }
  ]
}
```

### Regla sobre confianza

El score devuelto por un MaaS multimodal no debe interpretarse automáticamente como probabilidad calibrada. El sistema puede mostrar niveles cualitativos:

```text
alta
media
baja
no concluyente
```

Cuando la confianza sea media, baja o no concluyente, el sistema debe pedir confirmación explícita o solicitar una nueva imagen.

---

## 9. Validación taxonómica y proveedores auxiliares

### Proveedor principal de identificación

```text
MaaS multimodal agnóstico
```

Puede implementarse sobre distintos proveedores mediante `ModelProvider`:

```text
OpenAIProvider
GeminiProvider
AnthropicProvider
VertexAIProvider
OllamaProvider
MockProvider
```

### Validación taxonómica obligatoria

Usar:

```text
GBIF Species API
```

GBIF no identifica plantas desde imágenes. Su rol es posterior a la inferencia visual:

- validar nombre científico;
- normalizar taxonomía;
- resolver sinónimos;
- obtener género, familia y especie;
- guardar identificadores estables.

### APIs botánicas especializadas

No se usarán como dependencia principal del MVP por límites operativos, cuotas o disponibilidad.

Pueden quedar como herramientas opcionales para:

- benchmark;
- comparación manual;
- validación secundaria si hay cuota disponible;
- experimentación futura.

Ejemplos opcionales:

```text
Pl@ntNet API
Plant.id / Kindwise
Perenual Plant Identify API
```

### Regla

La aplicación debe poder funcionar sin depender de una API botánica especializada externa.

---

## 10. Flujo propuesto para identificación botánica con MaaS

```text
Usuario sube/toma imagen
  ↓
FastAPI recibe imagen
  ↓
Guarda imagen temporal en bucket
  ↓
VisionPlantIdentificationProvider.identify_candidates(image)
  ↓
MaaS multimodal devuelve:
  - descripción visual breve
  - top 3 candidatas
  - rasgos visibles usados para inferir
  - nivel cualitativo de confianza
  ↓
Validar nombres científicos con GBIF
  ↓
¿Hay candidatas taxonómicamente válidas?
  ├─ Sí
  │   ↓
  │  Mostrar candidatas al usuario
  │
  └─ No
      ↓
     Pedir nueva foto o búsqueda manual
  ↓
Usuario confirma especie
  ↓
Consultar vector store
  ↓
¿Hay conocimiento suficiente?
  ├─ Sí → generar ficha con RAG
  └─ No → adquisición incremental de conocimiento
  ↓
Ficha de planta
```

### Reglas de producto

- El sistema debe presentar resultados como “posibles coincidencias”.
- El sistema no debe afirmar “esta es tu planta” antes de la confirmación del usuario.
- El sistema no debe crear ficha definitiva ni recordatorios hasta que la especie esté confirmada.
- Si existen candidatas similares, debe mostrar varias opciones.
- Si la imagen no permite inferencia confiable, debe pedir otra foto.
- Si GBIF no valida el nombre científico, la candidata debe marcarse como no validada o descartarse.
- La identificación debe comunicarse como asistida y falible.

### Copy recomendado

```text
Posibles coincidencias
Parece ser esta especie, pero confirmá si coincide con tu planta.
No pudimos identificar la planta con suficiente confianza.
Tomá otra foto incluyendo hojas, tallo o flor si está disponible.
```

---

## 11. Medidor de luz

### Decisión

Prioridad técnica:

```text
1. AmbientLightSensor
2. Cámara como fallback
3. Registro manual
```

### Flujo

```text
Abrir medidor de luz
  ↓
¿Browser soporta AmbientLightSensor?
  ├─ Sí
  │   ↓
  │  Solicitar permiso
  │   ↓
  │  Medir lux
  │
  └─ No
      ↓
     ¿Hay cámara disponible?
      ├─ Sí → estimar luz por luminancia de imagen
      └─ No → registro manual
```

### Clasificación

```text
baja
media
alta
directa
```

### Regla

La medición por cámara debe presentarse como aproximada.

---

## 12. Observabilidad

### Decisión

Implementar observabilidad desde el inicio.

### Registrar

```text
requests
latencia
errores
tokens
costos estimados
búsquedas web
documentos generados
embeddings creados
tool runs
fallos de recuperación
fallos de proveedor MaaS
```

### Stack sugerido

```text
logs JSON
OpenTelemetry
Prometheus
Grafana
```

---

## 13. Testing

### Backend

```text
pytest
httpx
coverage
```

### Frontend

```text
Playwright
React Testing Library
```

### Mocks obligatorios

```text
MockModelProvider
MockVisionPlantIdentificationProvider
MockSearchProvider
MockEmbeddingProvider
```

---

## 14. Deploy

### Local

```text
Docker Compose
```

Debe levantar:

```text
frontend
backend
postgres
object-storage local opcional
observabilidad mínima opcional
```

### Cloud

```text
Kubernetes / GKE
Cloud SQL for PostgreSQL
Cloud Storage Bucket
```

---

## 15. Decisión técnica resumida

```text
Frontend:
  Next.js + React + SCSS Modules

Backend:
  FastAPI + Uvicorn

MaaS:
  Provider-agnostic interface

Agente:
  LangGraph

RAG:
  LlamaIndex

Base:
  PostgreSQL + pgvector

Cloud DB:
  Cloud SQL for PostgreSQL

Storage:
  Cloud Storage Bucket

Identificación:
  VisionPlantIdentificationProvider
  MaaS multimodal agnóstico como fuente principal
  GBIF para validación taxonómica
  Confirmación obligatoria del usuario
  APIs botánicas especializadas solo como benchmark o validación secundaria opcional

Medidor de luz:
  AmbientLightSensor → cámara → manual

Evaluación:
  retrieval metrics + BERTScore + ROUGE-L + LLM-as-a-judge + tool_success_rate
```

---

## Fuentes técnicas verificadas

- Next.js Sass / SCSS Modules: <https://nextjs.org/docs/app/guides/sass>
- LangGraph: <https://docs.langchain.com/oss/python/langgraph/overview>
- LlamaIndex: <https://developers.llamaindex.ai/python/framework/>
- LlamaIndex Postgres Vector Store: <https://developers.llamaindex.ai/python/framework/integrations/vector_stores/postgres/>
- Cloud SQL + pgvector: <https://cloud.google.com/sql/docs/postgres/generate-manage-vector-embeddings>
- Cloud Storage: <https://cloud.google.com/storage>
- GBIF Species API: <https://techdocs.gbif.org/en/openapi/v1/species>
