# Fotosíntesis AI — Requisitos funcionales y no funcionales

## Requisitos funcionales

### RF-001 — Registro de usuario

El sistema debe permitir crear una cuenta con datos mínimos: nombre, email y contraseña.

### RF-002 — Inicio de sesión

El sistema debe permitir iniciar sesión con credenciales válidas.

### RF-003 — Recuperación de contraseña

El sistema debe permitir iniciar un flujo de recuperación de contraseña.

### RF-004 — Home

El sistema debe mostrar un Home con accesos a identificación, medidor de luz, recordatorios, Mi Jardín y asistente generativo.

### RF-005 — Identificación por imagen con MaaS

El sistema debe permitir tomar o subir una imagen para obtener posibles coincidencias de planta mediante un proveedor MaaS multimodal agnóstico.

### RF-006 — Especies candidatas

El sistema debe mostrar especies candidatas con nombre, rasgos visibles observados, nivel de confianza cualitativo y estado de validación taxonómica.

### RF-007 — Validación taxonómica

El sistema debe validar los nombres científicos candidatos contra GBIF antes de usarlos para generar fichas, recordatorios o conocimiento persistente.

### RF-008 — Confirmación de especie

El usuario debe confirmar una especie candidata antes de generar la ficha final, guardarla en Mi Jardín o crear recordatorios asociados.

### RF-009 — Ficha de planta

El sistema debe generar una ficha de planta con nombre común, alias regional, nombre científico, descripción, condiciones, cuidados, plagas y recomendaciones.

### RF-010 — Alias regional

El sistema debe mostrar alias de planta priorizando región, país o idioma del usuario.

### RF-011 — Mi Jardín

El sistema debe permitir guardar plantas en un jardín personal.

### RF-012 — Gestión de plantas guardadas

El sistema debe permitir listar, buscar, consultar y eliminar plantas guardadas.

### RF-013 — Asistente generativo

El sistema debe permitir conversar con un asistente especializado en cuidado de plantas.

### RF-014 — RAG

El asistente debe responder usando recuperación de información desde una base vectorial.

### RF-015 — Agente con herramientas

El backend debe incluir un agente capaz de decidir cuándo usar herramientas: búsqueda, retrieval, persistencia, recordatorios y consulta de datos del usuario.

### RF-016 — Adquisición incremental

El sistema debe buscar, validar, guardar y embeber nuevo conocimiento cuando no exista evidencia suficiente en el vector store.

### RF-017 — Revivir una planta

El sistema debe permitir diagnosticar síntomas y sugerir pasos de recuperación.

### RF-018 — Diagnóstico con imagen

El sistema debe permitir usar una imagen como contexto para diagnóstico, si se implementa.

### RF-019 — Recordatorios

El sistema debe permitir crear, editar, eliminar y completar recordatorios.

### RF-020 — Recordatorios sugeridos

El sistema debe poder sugerir recordatorios según especie, cuidado recomendado o conversación con el asistente.

### RF-021 — Medidor de luz

El sistema debe permitir estimar luz ambiental mediante cámara o sensor cuando esté disponible.

### RF-022 — Registro manual de luz

El sistema debe permitir registrar luz manualmente si no hay soporte técnico o permisos.

### RF-023 — Health check

El backend debe exponer un endpoint de health check.

### RF-024 — Métricas

El backend debe exponer métricas básicas de servicio.

### RF-025 — Evaluación

El sistema debe incluir pipeline de evaluación con métricas automáticas, LLM-as-a-judge y dataset de prueba.

### RF-026 — Tests

El proyecto debe incluir tests unitarios, de integración y end-to-end mínimo.

### RF-027 — Despliegue

El proyecto debe incluir Docker Compose y manifiestos o Helm charts para Kubernetes/GKE.

---

## Requisitos no funcionales

### RNF-001 — Mobile-first

La interfaz debe diseñarse priorizando dispositivos móviles.

### RNF-002 — Responsive

La aplicación debe funcionar correctamente en distintos tamaños de pantalla.

### RNF-003 — Usabilidad

La interfaz debe ser usable por usuarios no técnicos.

### RNF-004 — Accesibilidad básica

El sistema debe contemplar contraste, tamaño de fuente, foco visible y navegación clara.

### RNF-005 — Trazabilidad

Toda información adquirida dinámicamente debe guardar fuentes, fecha y nivel de confianza.

### RNF-006 — Observabilidad

El sistema debe registrar logs estructurados, latencia, errores, tokens y eventos relevantes.

### RNF-007 — Recuperación ante fallos

Los errores deben ser recuperables con reintento o fallback.

### RNF-008 — Seguridad de inputs

El sistema debe validar imágenes, formularios, prompts y parámetros recibidos.

### RNF-009 — Control de prompt injection

El asistente debe resistir instrucciones que intenten ignorar reglas del sistema o manipular herramientas.

### RNF-010 — Control de fuentes externas

La búsqueda web debe restringirse a fuentes confiables o reglas de validación explícitas.

### RNF-011 — Performance

Las respuestas interactivas deben tener tiempos razonables y estados de carga visibles.

### RNF-012 — Escalabilidad

La arquitectura debe separar frontend, backend, base de datos, vector store y servicios externos.

### RNF-013 — Reproducibilidad

El stack local debe levantarse con Docker Compose.

### RNF-014 — Portabilidad cloud

El sistema debe poder desplegarse en Kubernetes/GKE.

### RNF-015 — Mantenibilidad

El código debe separarse por dominios: auth, plantas, RAG, agente, recordatorios, evaluación y monitoreo.

### RNF-016 — Calidad de respuestas

Las respuestas del asistente deben evaluarse con métricas y revisión automatizada.

### RNF-017 — Privacidad

La ubicación del usuario debe usarse solo a nivel necesario para alias y contexto regional. No se requiere GPS exacto para el MVP.

### RNF-018 — Degradación controlada

Si falla una funcionalidad avanzada, la app debe ofrecer una alternativa: búsqueda manual, registro manual o respuesta parcial.

### RNF-019 — Identificación asistida y falible

La identificación por imagen debe comunicarse como asistida y no definitiva. El sistema debe evitar afirmaciones categóricas cuando la confianza sea baja o la taxonomía no esté validada.

### RNF-020 — Independencia de APIs botánicas especializadas

La aplicación no debe depender obligatoriamente de una API botánica especializada externa para funcionar. Estas APIs podrán usarse solo como benchmark, validación secundaria o mejora futura.
