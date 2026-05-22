## ADDED Requirements

### Requirement: Stack frontend
El frontend SHALL implementarse con TypeScript, React, Next.js, SCSS Modules, TanStack Query y Zustand.

#### Scenario: Separacion de estado frontend
- **WHEN** una pantalla necesita datos persistidos del backend
- **THEN** el sistema usa TanStack Query como fuente de verdad remota y limita Zustand a estado temporal de interfaz

### Requirement: Stack backend y API minima
El backend SHALL implementarse con FastAPI + Uvicorn y SHALL exponer endpoints minimos para health, metrics, chat, identificacion, plantas, jardin, recordatorios, mediciones de luz y evaluacion.

#### Scenario: Health check
- **WHEN** se consulta `GET /health`
- **THEN** el backend responde estado de servicio e indica disponibilidad de LLM, base de datos y vector store cuando corresponda

### Requirement: Interfaces agnosticas de proveedor
El backend MUST depender de interfaces propias para generacion de texto, JSON, analisis de imagen, embeddings y judge, no de SDKs de proveedores en la logica de negocio.

#### Scenario: Proveedor MaaS reemplazable
- **WHEN** se cambia el proveedor configurado de MaaS o embeddings
- **THEN** la logica de dominio continua usando la misma interfaz y no requiere cambios en reglas de producto

### Requirement: Orquestacion de agente
El sistema SHALL usar LangGraph para modelar decisiones, herramientas, reintentos y estado del agente.

#### Scenario: Flujo no lineal del agente
- **WHEN** el asistente detecta evidencia insuficiente
- **THEN** el grafo puede pasar por busqueda, validacion, persistencia, embeddings, nuevo retrieval y generacion de respuesta

### Requirement: RAG e indexacion
El sistema SHALL usar LlamaIndex para carga documental, chunking, embeddings, indexacion en pgvector, retrieval y filtros por metadata.

#### Scenario: Retrieval con filtros
- **WHEN** el agente consulta conocimiento para una especie y topico
- **THEN** el sistema puede filtrar por especie, tema, fuente, confianza, fecha y estado de revision

### Requirement: Persistencia relacional y vectorial
El sistema SHALL usar PostgreSQL + pgvector para usuarios, perfiles, plantas, alias, jardin, recordatorios, mediciones, conversaciones, documentos, fuentes, chunks, embeddings, tool runs y evaluaciones.

#### Scenario: Documento de conocimiento persistido
- **WHEN** se incorpora un documento de conocimiento
- **THEN** el sistema guarda documento, fuentes, chunks y embeddings con integridad relacional y metadata obligatoria

### Requirement: Almacenamiento de imagenes
El sistema SHALL almacenar fotos subidas, imagenes de identificacion, diagnostico, referencia y temporales en un bucket de objetos, no como blobs primarios en PostgreSQL.

#### Scenario: Imagen de identificacion recibida
- **WHEN** el backend recibe una imagen para identificacion
- **THEN** el sistema guarda metadata en base de datos y el archivo en storage de objetos con ruta, mime type, tamano y expiracion cuando aplique

### Requirement: Observabilidad
El sistema SHALL registrar logs estructurados, metricas, trazas, latencia, errores, tokens, costos estimados, busquedas web, documentos generados, embeddings creados, tool runs y fallos de proveedores.

#### Scenario: Request al asistente finalizada
- **WHEN** una request de chat termina con exito o error
- **THEN** el sistema registra latencia, estado, proveedor, tokens, herramientas usadas y errores si existen

### Requirement: Reproducibilidad y despliegue
El sistema SHALL poder levantarse localmente con Docker Compose y SHALL incluir manifiestos o Helm charts para Kubernetes/GKE.

#### Scenario: Stack local
- **WHEN** se ejecuta el stack local documentado
- **THEN** se levantan frontend, backend, postgres, storage local opcional y observabilidad minima opcional

### Requirement: Testing con mocks
El proyecto SHALL incluir tests unitarios, de integracion y end-to-end usando mocks obligatorios para proveedores de modelo, vision, busqueda y embeddings.

#### Scenario: Tests sin proveedores reales
- **WHEN** se ejecuta la suite en entorno local o CI sin credenciales MaaS reales
- **THEN** los tests usan `MockModelProvider`, `MockVisionPlantIdentificationProvider`, `MockSearchProvider` y `MockEmbeddingProvider`
