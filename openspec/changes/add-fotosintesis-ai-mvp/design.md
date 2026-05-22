## Context

Fotosintesis AI sera una aplicacion mobile-first para jardineria domestica. La identificacion visual por imagen es una entrada asistida y falible; el nucleo del MVP es la asistencia generativa con RAG, agente con herramientas y adquisicion incremental de conocimiento trazable.

El cambio parte de las pre-specs en `DOCS/PRE-SPECS/`. Las decisiones tecnicas se toman de `decisiones-tecnicas.spec.md` y el protocolo de evaluacion se toma de `evaluacion.specs.md`.

## Goals / Non-Goals

**Goals:**

- Definir el MVP completo por capacidades de dominio antes de implementar codigo.
- Mantener una arquitectura desacoplada entre frontend, backend, MaaS, agente, RAG, persistencia, observabilidad y evaluacion.
- Usar un proveedor MaaS multimodal agnostico para identificacion visual, sin acoplar dominio a un SDK concreto.
- Validar taxonomia con GBIF antes de usar especies en fichas, Mi Jardin, recordatorios o conocimiento persistente.
- Usar RAG y adquisicion incremental para responder con evidencia y reutilizar conocimiento nuevo.
- Incluir evaluacion multicapa desde el MVP: retrieval, generacion, agente/tools, identificacion visual y flujos end-to-end.

**Non-Goals:**

- No implementar codigo, modelos, pipelines, infraestructura ni UI en este cambio.
- No entrenar un clasificador propio de plantas para el MVP.
- No depender obligatoriamente de APIs botanicas especializadas como Pl@ntNet, Plant.id, Kindwise o Perenual.
- No tratar la identificacion visual como diagnostico taxonomico definitivo.
- No requerir GPS exacto para el MVP; region, pais o idioma alcanzan para alias y contexto regional.

## Decisions

### Frontend

Usar Next.js, React, TypeScript, SCSS Modules, TanStack Query y Zustand.

Rationale: TypeScript tipa DTOs, formularios, respuestas y estados de UI. TanStack Query sera la fuente de verdad para datos remotos como fichas, jardin, recordatorios, mediciones, conversaciones y estados de adquisicion. Zustand se limita a estado temporal de UI como flujo de identificacion, candidata seleccionada, camara, modales, filtros y formularios en progreso. SCSS Modules conserva la identidad visual existente y evita introducir Tailwind.

Alternatives considered: Tailwind se descarta porque el producto parte de una identidad visual y UI kit existentes que requieren control fino de tokens, modulos y composicion.

### Backend API

Usar FastAPI + Uvicorn.

Rationale: FastAPI permite endpoints documentados, validacion de schemas, integracion asincronica con proveedores y buena ergonomia para tests con pytest/httpx. El backend orquesta usuarios, plantas, jardin, recordatorios, chat, agente, RAG, evaluacion, health checks y metricas.

Endpoints minimos: `GET /health`, `GET /metrics`, `POST /chat`, `POST /plants/identify`, `GET /plants/{id}`, `POST /garden`, `GET /garden`, `POST /reminders`, `GET /reminders`, `POST /light-measurements`, `POST /evaluation/run`.

Alternatives considered: un backend fullstack dentro de Next.js reduciria piezas, pero acoplaria demasiado el agente, RAG, providers y evaluacion a la capa web.

### MaaS agnostico

El dominio dependera de interfaces propias para texto, JSON, vision, embeddings y judge, no de SDKs concretos.

Rationale: el MVP debe poder cambiar entre OpenAI, Anthropic, Gemini, Vertex AI, Ollama o mocks sin reescribir reglas de dominio. La identificacion visual usara un `VisionPlantIdentificationProvider` que devuelve candidatas, rasgos visibles, proveedor, confianza cualitativa y confirmacion requerida.

Alternatives considered: acoplar a un proveedor especifico acelera el prototipo, pero aumenta riesgo de cuotas, cambios de API, costos y bloqueo de proveedor.

### Identificacion visual y taxonomia

La identificacion se resolvera como flujo asistido: imagen, top 3 candidatas MaaS, rasgos visibles, confianza cualitativa, validacion GBIF y confirmacion del usuario.

Rationale: un MaaS multimodal no entrega una probabilidad botanica calibrada. GBIF no identifica desde imagen, pero si normaliza nombres, sinonimos, genero, familia, especie e identificadores estables. Ninguna ficha definitiva, planta guardada o recordatorio asociado debe crearse antes de validacion taxonomica y confirmacion del usuario.

Alternatives considered: usar una API botanica especializada como dependencia principal se descarta por disponibilidad, cuotas y porque el MVP debe funcionar sin ella. Puede quedar como benchmark o validacion secundaria opcional.

### Agente

Usar LangGraph para orquestacion.

Rationale: los flujos no son lineales. El agente debe clasificar intencion, cargar contexto de usuario, hacer retrieval, evaluar suficiencia, buscar fuentes confiables, validar, persistir, embeber, generar respuesta, crear recordatorios, pedir aclaraciones y manejar fallos.

Alternatives considered: una chain simple es insuficiente para decisiones, herramientas, reintentos y estado.

### RAG e indexacion

Usar LlamaIndex sobre PostgreSQL + pgvector.

Rationale: LlamaIndex cubre carga documental, parsing, chunking, metadata, embeddings, indexacion y retrieval. PostgreSQL mantiene relaciones, trazabilidad, filtros e integridad junto con pgvector en una sola base.

Metadata obligatoria por chunk: `species_id`, `scientific_name`, `topic`, `source_domain`, `source_url`, `confidence`, `review_status`, `retrieved_at`, `created_at`.

Alternatives considered: un vector database separado puede escalar en el futuro, pero para el MVP aumenta complejidad operacional sin necesidad clara.

### Persistencia y storage

Usar PostgreSQL + pgvector para entidades relacionales, documentos, chunks y embeddings. Usar bucket de objetos para fotos subidas, imagenes de identificacion, diagnostico, referencia y archivos temporales.

Rationale: el dominio relaciona usuarios, perfiles, plantas, alias, jardin, recordatorios, mediciones, conversaciones, documentos, fuentes, chunks, tool runs y evaluaciones. Las imagenes no deben guardarse como blobs en tablas relacionales.

### Medidor de luz

Prioridad tecnica: AmbientLightSensor, camara como fallback, registro manual.

Rationale: AmbientLightSensor entrega lux cuando existe soporte. La camara solo estima por luminancia y debe mostrarse como aproximada. El registro manual garantiza degradacion controlada.

### Observabilidad

Implementar logs JSON, OpenTelemetry, metricas Prometheus/Grafana y registros de tool runs desde el inicio.

Rationale: el sistema usa proveedores externos, busquedas web, embeddings, agente y RAG. Se necesita trazabilidad de requests, latencia, errores, tokens, costos estimados, documentos generados, fallos de retrieval y fallos de MaaS.

### Evaluacion

Usar una evaluacion multicapa con dataset inicial de 50 casos.

Rationale: una sola metrica no mide grounding, exactitud botanica, utilidad, seguridad, tool usage ni identificacion visual. El MVP debe calcular `retrieval_recall@5`, `precision@5`, BERTScore, ROUGE-L, LLM-as-a-judge, `tool_success_rate`, `unnecessary_web_search_rate`, `failed_action_claim_rate` y metricas de identificacion visual como top 3 accuracy, taxonomy validation rate y low confidence detection rate.

Alternatives considered: BLEU, perplexity, FID, IS y CLIP Score no seran metricas principales porque no miden bien verdad, grounding ni aplican al problema generativo/textual del MVP.

### Testing y despliegue

Backend: pytest, httpx y coverage. Frontend: Playwright y React Testing Library. Mocks obligatorios: `MockModelProvider`, `MockVisionPlantIdentificationProvider`, `MockSearchProvider`, `MockEmbeddingProvider`.

Local: Docker Compose con frontend, backend, postgres, object storage local opcional y observabilidad minima opcional. Cloud: Kubernetes/GKE, Cloud SQL for PostgreSQL + pgvector y Cloud Storage Bucket.

## Risks / Trade-offs

- MaaS multimodal devuelve candidatas incorrectas o confianza no calibrada -> mostrar posibles coincidencias, exigir confirmacion del usuario, usar confianza cualitativa y validar con GBIF.
- GBIF no valida candidatas utiles por alias, sinonimos o nombres incompletos -> permitir busqueda manual, normalizar sinonimos y mostrar candidata no validada sin crear ficha definitiva.
- Adquisicion incremental incorpora informacion de baja calidad -> restringir fuentes, contrastar cuando sea posible, guardar confidence, review_status, fuente, URL y fecha.
- El agente usa busqueda web innecesariamente -> medir `unnecessary_web_search_rate`, registrar tool runs y requerir evaluacion de suficiencia antes de buscar.
- Prompt injection intenta manipular herramientas o fuentes -> separar instrucciones de sistema, validar intenciones, restringir tools y no obedecer instrucciones que ignoren reglas internas.
- Latencias altas por MaaS, RAG o busqueda web -> estados de carga visibles, timeouts, respuestas parciales seguras y reintentos controlados.
- AmbientLightSensor no esta disponible en la mayoria de browsers -> fallback por camara y registro manual.
- Costos o cuotas de proveedores -> provider agnostico, observabilidad de tokens/costos y mocks para desarrollo/evaluacion.
- Evaluacion automatica no captura todos los errores botanicos -> combinar metricas automaticas con LLM-as-a-judge, dataset curado, analisis de fallos y limitaciones documentadas.

## Migration Plan

No hay migracion de datos o codigo porque este cambio crea la especificacion inicial. La implementacion futura debe avanzar por capacidades, empezando por contratos de datos, mocks y flujos end-to-end minimos antes de conectar proveedores reales.

## Open Questions

- Definir si el copy final usara espanol rioplatense moderado o espanol neutro regionalizable.
- Definir proveedor MaaS inicial para desarrollo y proveedor judge para evaluacion, manteniendo interfaces agnosticas.
- Definir lista final de dominios confiables y politica de revision manual para conocimiento `auto_ingested`.
- Definir estrategia exacta de notificaciones push para recordatorios en web/mobile.
