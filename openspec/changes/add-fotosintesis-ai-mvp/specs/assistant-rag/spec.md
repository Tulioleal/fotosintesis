## ADDED Requirements

### Requirement: Asistente generativo especializado

El sistema SHALL permitir conversar con un asistente especializado en cuidado de plantas, riego, luz, suelo, plagas, sintomas, recuperacion y uso de la app.

#### Scenario: Pregunta sobre planta guardada

- **WHEN** el usuario pregunta por una planta guardada en Mi Jardin
- **THEN** el asistente recupera contexto de la especie y datos del usuario para responder con una recomendacion concreta y orientativa

### Requirement: RAG obligatorio para respuestas botanicas

El asistente MUST responder preguntas botanicas usando retrieval desde la base vectorial cuando exista evidencia disponible.

#### Scenario: Evidencia suficiente

- **WHEN** el retrieval devuelve documentos relevantes para la pregunta
- **THEN** el asistente genera una respuesta apoyada en esos documentos y evita datos no soportados por el corpus

#### Scenario: Evidencia insuficiente

- **WHEN** el retrieval no devuelve evidencia suficiente
- **THEN** el asistente activa adquisicion incremental o explica la limitacion y ofrece una recomendacion general segura

### Requirement: Agente con herramientas

El backend SHALL incluir un agente capaz de decidir cuando usar herramientas de conocimiento, busqueda web confiable, validacion taxonomica, persistencia, embeddings, Mi Jardin, recordatorios y mediciones de luz.

#### Scenario: Usuario pide crear recordatorio desde chat

- **WHEN** el usuario solicita un recordatorio y faltan datos como planta, fecha, hora o repeticion
- **THEN** el agente pide aclaracion antes de crear el recordatorio

#### Scenario: Tool falla

- **WHEN** una herramienta falla durante una accion solicitada
- **THEN** el asistente informa que la accion no se completo y registra el fallo sin afirmar exito

### Requirement: Manejo de ambiguedad y fuera de dominio

El asistente SHALL pedir aclaracion ante preguntas ambiguas y SHALL rechazar o redirigir preguntas fuera del dominio de forma util.

#### Scenario: Pregunta ambigua

- **WHEN** el usuario pregunta "La tengo que regar hoy?" y tiene varias plantas guardadas
- **THEN** el asistente pide aclarar a que planta se refiere antes de recomendar

#### Scenario: Pregunta fuera de dominio

- **WHEN** el usuario realiza una consulta no relacionada con plantas, jardineria o uso de la app
- **THEN** el asistente responde brevemente que no puede ayudar con ese tema y ofrece volver al dominio soportado

### Requirement: Seguridad contra prompt injection

El asistente MUST resistir instrucciones que intenten ignorar reglas del sistema, manipular herramientas, inventar fuentes o saltar validaciones.

#### Scenario: Prompt malicioso

- **WHEN** el usuario pide ignorar fuentes, reglas internas o validaciones
- **THEN** el asistente mantiene las reglas del sistema y responde solo con informacion permitida y relevante
