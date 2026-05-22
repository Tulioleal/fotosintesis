## Why

Fotosintesis AI necesita una especificacion inicial del MVP que convierta las pre-specs existentes en un contrato de producto, dominio, evaluacion y arquitectura listo para implementar. El objetivo es definir una app mobile-first que use identificacion visual asistida como entrada, pero cuyo nucleo sea asistencia generativa con RAG, agente y adquisicion incremental de conocimiento.

## What Changes

- Definir autenticacion con registro, login, recuperacion de acceso y proteccion de flujos autenticados.
- Definir Home mobile-first con accesos principales a identificacion, medidor de luz, recordatorios, Mi Jardin, asistente y busqueda.
- Definir identificacion visual por imagen mediante MaaS multimodal agnostico, comunicada como posibles coincidencias y no como verdad definitiva.
- Definir validacion taxonomica obligatoria con GBIF antes de generar fichas, guardar plantas o crear recordatorios asociados.
- Definir ficha de planta con alias regional, nombre cientifico, descripcion, cuidados, condiciones, plagas, fuentes y acciones contextuales.
- Definir Mi Jardin para guardar, listar, buscar, consultar y eliminar plantas del usuario.
- Definir asistente generativo con RAG y herramientas para responder preguntas, usar contexto del usuario y actuar sobre recordatorios o mediciones.
- Definir adquisicion incremental de conocimiento cuando el vector store no tenga evidencia suficiente, con fuentes confiables, trazabilidad, embeddings y reutilizacion futura.
- Definir recordatorios manuales y sugeridos por IA, con edicion, eliminacion, completado y recurrencia.
- Definir medidor de luz con prioridad AmbientLightSensor, fallback por camara y registro manual.
- Definir evaluacion multicapa para retrieval, respuesta generada, agente/tools, identificacion visual y flujos end-to-end.
- Definir arquitectura tecnica base usando Next.js, React, TypeScript, SCSS Modules, TanStack Query, Zustand, FastAPI, LangGraph, LlamaIndex, PostgreSQL + pgvector, almacenamiento de objetos, observabilidad, Docker Compose y Kubernetes/GKE.
- No se implementa codigo en este cambio; solo se crean artefactos de especificacion.

## Capabilities

### New Capabilities

- `auth`: registro, inicio de sesion, recuperacion de acceso, sesion autenticada y validaciones de formularios.
- `home`: pantalla principal, navegacion mobile-first, accesos principales, estados vacios, loading y error.
- `plant-identification`: carga o captura de imagen, identificacion asistida con MaaS multimodal, candidatas, rasgos visibles, confianza cualitativa y confirmacion del usuario.
- `taxonomy-validation`: validacion y normalizacion taxonomica con GBIF, resolucion de sinonimos, identificadores estables y manejo de candidatas no validadas.
- `plant-profile`: generacion y visualizacion de ficha de planta con RAG, alias regionales, fuentes, secciones de cuidado y acciones contextuales.
- `garden`: Mi Jardin, guardado de plantas confirmadas, listado, busqueda, detalle, eliminacion y relacion con recordatorios y mediciones.
- `assistant-rag`: asistente conversacional especializado, RAG, uso de herramientas, contexto del usuario, manejo de incertidumbre y seguridad contra prompt injection.
- `incremental-knowledge`: adquisicion progresiva de documentos, validacion de fuentes, persistencia, metadata, chunking, embeddings y reutilizacion en RAG.
- `reminders`: recordatorios de cuidado manuales y sugeridos, recurrencia, completado, permisos de notificacion y justificacion de sugerencias.
- `light-meter`: medicion o registro de luz ambiental con AmbientLightSensor, camara y fallback manual, clasificacion y asociacion a plantas.
- `evaluation`: dataset, metricas automaticas, LLM-as-a-judge, evaluacion de tools/agente, identificacion visual y reporte de resultados.
- `technical-architecture`: decisiones tecnicas transversales, APIs minimas, provider agnostico MaaS, persistencia, storage, observabilidad, testing y despliegue.

### Modified Capabilities

- None.

## Impact

- Afecta el contrato funcional completo del MVP antes de escribir codigo.
- Establece futuros dominios de frontend, backend, datos, agente, RAG, evaluacion, observabilidad e infraestructura.
- Introduce integraciones externas obligatorias o previstas: proveedor MaaS multimodal agnostico, GBIF Species API, fuentes confiables para adquisicion incremental y proveedor LLM/embeddings mediante interfaces propias.
- Define endpoints minimos esperados para health, metrics, chat, identificacion, plantas, jardin, recordatorios, mediciones de luz y evaluacion.
- Define criterios de calidad, seguridad, trazabilidad, degradacion controlada y reproducibilidad local/cloud.
