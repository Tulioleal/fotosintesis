## ADDED Requirements

### Requirement: Evaluacion multicapa

El sistema SHALL incluir un pipeline de evaluacion que mida retrieval, respuesta generada, comportamiento del agente, tools, identificacion visual y flujos end-to-end.

#### Scenario: Ejecucion de evaluacion

- **WHEN** se ejecuta el pipeline contra el dataset de prueba
- **THEN** el sistema calcula metricas automaticas, ejecuta LLM-as-a-judge, guarda resultados, errores y analisis por flujo

### Requirement: Metricas de retrieval

El sistema SHALL calcular `retrieval_recall@5` y `precision@5` para preguntas al asistente, fichas, diagnosticos y conocimiento incremental.

#### Scenario: Retrieval evaluado

- **WHEN** un caso define documentos esperados y documentos recuperados
- **THEN** el sistema calcula recall@5 y precision@5 y los compara contra umbrales minimos 0.80 y 0.60 respectivamente

### Requirement: Metricas de generacion

El sistema SHALL calcular BERTScore y ROUGE-L para respuestas, fichas, resumenes y recomendaciones con referencias esperadas.

#### Scenario: Respuesta generada evaluada

- **WHEN** existe respuesta generada y respuesta de referencia
- **THEN** el sistema calcula BERTScore F1 y ROUGE-L y los compara contra umbrales iniciales 0.82 y 0.35

### Requirement: LLM-as-a-judge

El sistema SHALL evaluar grounding, exactitud botanica, utilidad, claridad, seguridad, manejo de incertidumbre, uso de herramientas, alucinaciones y recomendaciones inseguras mediante un judge idealmente distinto al generador.

#### Scenario: Judge detecta respuesta insuficiente

- **WHEN** una respuesta obtiene score final menor a 4 o falla criterios minimos de grounding, seguridad o exactitud botanica
- **THEN** el sistema marca el caso como fallido y guarda razon de fallo

### Requirement: Evaluacion de agente y tools

El sistema SHALL calcular `tool_success_rate`, `unnecessary_web_search_rate` y `failed_action_claim_rate`.

#### Scenario: Tool fallida no debe declararse exitosa

- **WHEN** una herramienta falla durante un caso de evaluacion
- **THEN** el sistema verifica que la respuesta no afirme que la accion fue completada y exige `failed_action_claim_rate` igual a 0.00

### Requirement: Evaluacion de identificacion visual

El sistema SHALL evaluar identificacion visual como candidatas asistidas usando top 1 accuracy, top 3 accuracy, taxonomy validation rate, low confidence detection rate y user confirmation rate.

#### Scenario: Identificacion visual evaluada

- **WHEN** un caso incluye imagen y etiqueta esperada
- **THEN** el sistema verifica si la especie correcta aparece en top 3, si GBIF valida candidatas y si baja confianza se detecta correctamente

### Requirement: Dataset y reporte

El sistema SHALL mantener un dataset inicial recomendado de 50 casos y SHALL generar un documento final de evaluacion con protocolo, metricas, prompts, resultados, fallos, limitaciones y conclusiones.

#### Scenario: Reporte final generado

- **WHEN** termina una ejecucion de evaluacion
- **THEN** el sistema produce un resumen con total de casos, casos pasados, fallos por flujo, metricas agregadas y analisis de errores
