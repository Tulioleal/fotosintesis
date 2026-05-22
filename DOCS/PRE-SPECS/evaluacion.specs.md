# Fotosíntesis AI — evaluacion.specs.md

## Estado

Especificación de evaluación recomendada para el TP Integrador.

---

## 1. Principio general

La evaluación no se resuelve con una sola métrica.

Fotosíntesis AI debe evaluar tres capas distintas:

```text
1. Retrieval
2. Respuesta generada
3. Comportamiento del agente
```

Además, debe incluir:

```text
métricas automáticas
LLM-as-a-judge
dataset de prueba
documentación de protocolo, resultados, análisis y limitaciones
```

---

## 2. Objetivos de evaluación

La evaluación debe responder estas preguntas:

- ¿El RAG recupera documentos correctos?
- ¿El asistente responde usando evidencia?
- ¿La respuesta es botánicamente razonable?
- ¿La respuesta evita inventar información?
- ¿La respuesta es útil para el usuario?
- ¿El agente usa herramientas cuando corresponde?
- ¿La adquisición incremental se activa en casos correctos?
- ¿La respuesta reconoce incertidumbre cuando la evidencia es baja?
- ¿El sistema evita recomendaciones riesgosas?
- ¿Los flujos principales funcionan end-to-end?

---

## 3. Evaluación recomendada

Usar:

```text
retrieval_recall@5
precision@5
BERTScore
ROUGE-L
LLM-as-a-judge
tool_success_rate
```

No usar como métricas principales:

```text
BLEU
perplexity
FID
IS
CLIP Score
```

Motivo:

- BLEU es demasiado rígida para respuestas generativas con paráfrasis.
- Perplexity mide fluidez/probabilidad, no verdad ni grounding.
- FID, IS y CLIP Score aplican a generación de imágenes, no a identificación de plantas por imagen.

---

## 4. Capa A — Evaluación de retrieval

### Objetivo

Medir si el sistema recupera los documentos correctos antes de generar la respuesta.

### Métrica: retrieval_recall@5

Mide si los documentos esperados aparecen dentro de los primeros 5 documentos recuperados.

Ejemplo:

```text
Pregunta:
  ¿Cada cuánto riego una Pata de oso?

Documentos esperados:
  cotyledon_tomentosa_cuidados.md
  suculentas_riego.md

Documentos recuperados top 5:
  cotyledon_tomentosa_cuidados.md
  suculentas_riego.md
  cactus_general.md
  luz_indirecta.md
  monstera_cuidados.md

Resultado:
  recall@5 = 1.0
```

### Métrica: precision@5

Mide cuántos de los primeros 5 documentos recuperados son realmente relevantes.

Ejemplo:

```text
Top 5 recuperados:
  3 documentos relevantes
  2 documentos irrelevantes

precision@5 = 3 / 5 = 0.6
```

### Cuándo se usa

- Preguntas al asistente.
- Generación de fichas.
- Diagnóstico de plantas.
- Adquisición incremental, después de embeber nuevo conocimiento.

### Umbrales iniciales sugeridos

```yaml
retrieval_recall_at_5_min: 0.80
precision_at_5_min: 0.60
```

---

## 5. Capa B — Evaluación de respuesta generada

### Objetivo

Medir si la respuesta final coincide semánticamente con lo esperado y cubre hechos importantes.

---

### Métrica: BERTScore

BERTScore compara similitud semántica entre la respuesta generada y una respuesta de referencia.

Es útil porque dos respuestas pueden ser correctas aunque usen palabras distintas.

Uso en Fotosíntesis:

```text
respuestas de cuidado
diagnósticos orientativos
recomendaciones de recuperación
respuestas del asistente
```

Ejemplo:

```text
Referencia:
  La Pata de oso es una suculenta. Requiere riego moderado y sustrato con buen drenaje. Evitá el exceso de agua.

Respuesta generada:
  Regala solo cuando el sustrato esté seco. Como suculenta, tolera mejor la falta de agua que el exceso. Usá tierra con buen drenaje.

Resultado esperado:
  BERTScore alto, aunque las frases no coincidan literalmente.
```

### Métrica: ROUGE-L

ROUGE-L mide solapamiento de secuencias entre respuesta generada y referencia.

Uso en Fotosíntesis:

```text
fichas generadas
resúmenes de cuidado
descripciones estructuradas
```

No debe ser la métrica principal para conversaciones abiertas, pero sirve para verificar cobertura de contenido esperado.

### Umbrales iniciales sugeridos

```yaml
bertscore_f1_min: 0.82
rouge_l_min: 0.35
```

Los umbrales deben calibrarse con resultados reales.

---

## 6. Capa C — LLM-as-a-judge

### Objetivo

Evaluar criterios que las métricas automáticas no capturan bien:

- grounding;
- exactitud botánica;
- utilidad;
- seguridad;
- claridad;
- ausencia de alucinaciones;
- manejo de incertidumbre;
- uso correcto de herramientas.

### Modelo judge

Debe ser idealmente distinto al modelo que genera la respuesta.

Ejemplo:

```text
Generator: proveedor MaaS configurado para la app
Judge: otro modelo MaaS o configuración independiente
```

### Input del judge

```json
{
  "case_id": "watering_001",
  "flow": "assistant_rag",
  "user_query": "¿Cada cuánto tengo que regar una Pata de oso?",
  "retrieved_context": [
    "fragmento recuperado 1",
    "fragmento recuperado 2"
  ],
  "generated_answer": "respuesta del sistema",
  "expected_facts": [
    "es una suculenta",
    "evitar exceso de riego",
    "usar sustrato con buen drenaje"
  ],
  "must_not_include": [
    "regar todos los días",
    "mantener siempre húmeda"
  ]
}
```

### Rúbrica del judge

```json
{
  "groundedness": "0-5",
  "botanical_correctness": "0-5",
  "usefulness": "0-5",
  "clarity": "0-5",
  "safety": "0-5",
  "uncertainty_handling": "0-5",
  "tool_use_correctness": "0-5",
  "hallucination_detected": true,
  "unsafe_recommendation_detected": true,
  "final_score": "0-5",
  "failure_reason": "string | null"
}
```

### Criterios

#### groundedness

Evalúa si la respuesta está apoyada en el contexto recuperado.

#### botanical_correctness

Evalúa si las afirmaciones botánicas son razonables y no contradicen fuentes.

#### usefulness

Evalúa si el usuario puede ejecutar una acción concreta a partir de la respuesta.

#### clarity

Evalúa si la respuesta es comprensible.

#### safety

Evalúa si evita recomendaciones peligrosas, excesivas o categóricas.

#### uncertainty_handling

Evalúa si el sistema pide más información o reconoce limitaciones cuando corresponde.

#### tool_use_correctness

Evalúa si el agente usó o evitó herramientas correctamente.

### Umbral sugerido

```yaml
llm_judge_final_score_min: 4
groundedness_min: 4
safety_min: 4
botanical_correctness_min: 4
```

---

## 7. Capa D — Evaluación de agente y tools

### Métrica: tool_success_rate

Mide si las herramientas llamadas por el agente terminaron correctamente.

```text
tool_success_rate = tool_runs_successful / total_tool_runs
```

### Tools a evaluar

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

### Casos esperados

- Si falta evidencia, el agente debe activar búsqueda controlada.
- Si hay evidencia suficiente, no debe buscar en internet innecesariamente.
- Si el usuario pide un recordatorio, debe llamar a la tool correspondiente.
- Si la pregunta es ambigua, debe pedir aclaración.
- Si una tool falla, no debe afirmar que la acción fue completada.

### Umbrales iniciales sugeridos

```yaml
tool_success_rate_min: 0.90
unnecessary_web_search_rate_max: 0.15
failed_action_claim_rate_max: 0.00
```

---

## 8. Evaluación de identificación botánica

Aunque la identificación visual no es el componente generativo central, debe evaluarse porque participa del flujo principal. Como la decisión técnica es usar MaaS multimodal, la evaluación debe tratar la salida como candidatas asistidas, no como verdad definitiva automática.

### Métricas recomendadas

```text
top_1_accuracy
top_3_accuracy
taxonomy_validation_rate
low_confidence_detection_rate
user_confirmation_rate
```

### Definición

#### top_1_accuracy

La primera candidata coincide con la etiqueta esperada.

#### top_3_accuracy

La especie correcta aparece dentro de las tres primeras candidatas.

#### low_confidence_detection_rate

El sistema detecta correctamente casos en los que no debe elegir automáticamente.

#### taxonomy_validation_rate

Porcentaje de candidatas devueltas por el MaaS que pudieron normalizarse correctamente contra GBIF.

#### user_confirmation_rate

Porcentaje de veces en que el usuario confirma una candidata ofrecida.

### Umbrales iniciales sugeridos

```yaml
top_3_accuracy_min: 0.75
taxonomy_validation_rate_min: 0.80
low_confidence_detection_rate_min: 0.90
```

---

## 9. Dataset de evaluación

### Objetivo

El dataset permite ejecutar pruebas repetibles y comparar resultados del sistema.

### Tamaño inicial recomendado

```text
50 casos
```

### Distribución sugerida

```yaml
assistant_rag: 12
plant_profile_generation: 8
revive_plant: 8
incremental_knowledge: 8
reminders_agent: 5
light_measurement_context: 4
plant_identification_maas_maas: 5
```

### Estructura de caso

```json
{
  "id": "watering_001",
  "flow": "assistant_rag",
  "plant": "Cotyledon tomentosa",
  "user_region": "AR",
  "query": "¿Cada cuánto tengo que regarla?",
  "input_image": null,
  "expected_documents": [
    "cotyledon_tomentosa_care",
    "succulents_watering"
  ],
  "expected_facts": [
    "es una suculenta",
    "evitar exceso de riego",
    "usar sustrato con buen drenaje"
  ],
  "must_not_include": [
    "regar todos los días",
    "mantener siempre húmeda"
  ],
  "reference_answer": "La Pata de oso es una suculenta. Regala solo cuando el sustrato esté seco y evitá el exceso de agua. Usá sustrato con buen drenaje."
}
```

---

## 10. Casos mínimos del dataset

### Cuidado general

```text
riego
luz
suelo
humedad
trasplante
fertilización
```

### Ficha de planta

```text
generar descripción
generar condiciones requeridas
generar guía de cuidados
generar plagas comunes
```

### Revivir una planta

```text
exceso de riego
falta de riego
hojas amarillas
hojas blandas
plagas visibles
falta de luz
```

### Adquisición incremental

```text
planta no indexada
síntoma no indexado
alias regional faltante
plaga no documentada
fuentes contradictorias
fuentes insuficientes
```

### Agente

```text
crear recordatorio
pedir aclaración
evitar búsqueda innecesaria
manejar tool fallida
pregunta fuera de dominio
prompt malicioso
```

### Luz

```text
lux disponible
sensor no soportado
fallback cámara
registro manual
medición contradictoria con necesidad de la planta
```

---

## 11. Protocolo de evaluación

### Paso 1 — Preparar dataset

- Crear archivo `evaluation_dataset.jsonl`.
- Cada línea representa un caso.
- Cada caso define flujo, input, documentos esperados, facts esperados y restricciones.

### Paso 2 — Ejecutar sistema

- Correr cada caso contra el backend.
- Guardar respuesta generada.
- Guardar documentos recuperados.
- Guardar tools ejecutadas.
- Guardar errores.

### Paso 3 — Calcular retrieval

- `retrieval_recall@5`
- `precision@5`

### Paso 4 — Calcular métricas de texto

- `BERTScore`
- `ROUGE-L`

### Paso 5 — Ejecutar LLM-as-a-judge

- Enviar pregunta, contexto, respuesta y rúbrica.
- Guardar scores.
- Guardar justificación breve.

### Paso 6 — Analizar resultados

Agrupar por flujo:

```text
assistant_rag
plant_profile_generation
revive_plant
incremental_knowledge
reminders_agent
light_measurement_context
plant_identification_maas
```

### Paso 7 — Documentar limitaciones

Registrar:

- casos fallidos;
- causas de error;
- fuentes insuficientes;
- problemas de retrieval;
- alucinaciones detectadas;
- tools fallidas;
- errores por proveedor MaaS.

---

## 12. Salida esperada de evaluación

```json
{
  "run_id": "eval_2026_05_21_001",
  "summary": {
    "total_cases": 50,
    "passed_cases": 42,
    "failed_cases": 8,
    "retrieval_recall_at_5": 0.84,
    "precision_at_5": 0.68,
    "bertscore_f1": 0.86,
    "rouge_l": 0.41,
    "llm_judge_avg_score": 4.2,
    "tool_success_rate": 0.93
  },
  "failures_by_flow": {
    "assistant_rag": 2,
    "revive_plant": 3,
    "incremental_knowledge": 2,
    "reminders_agent": 1
  }
}
```

---

## 13. Criterios de aprobación internos

Una ejecución se considera aceptable si cumple:

```yaml
retrieval_recall_at_5: ">= 0.80"
precision_at_5: ">= 0.60"
bertscore_f1: ">= 0.82"
rouge_l: ">= 0.35"
llm_judge_avg_score: ">= 4.0"
tool_success_rate: ">= 0.90"
failed_action_claim_rate: "= 0.00"
```

---

## 14. Documento final de evaluación

Debe incluir:

```text
protocolo
dataset usado
métricas elegidas
justificación de métricas
prompts usados para LLM-as-a-judge
resultados agregados
resultados por flujo
casos fallidos
análisis de errores
limitaciones
conclusiones
```

---

## 15. Resumen

La evaluación recomendada para Fotosíntesis AI es una evaluación multicapa:

```text
Retrieval:
  retrieval_recall@5
  precision@5

Generación:
  BERTScore
  ROUGE-L

Agente:
  tool_success_rate
  unnecessary_web_search_rate
  failed_action_claim_rate

Calidad:
  LLM-as-a-judge con rúbrica

Dataset:
  50 casos iniciales distribuidos por flujo
```
