# Fotosíntesis AI — Adquisición incremental de conocimiento

## Definición

La adquisición incremental de conocimiento es el mecanismo mediante el cual el sistema incorpora información nueva cuando el RAG no posee evidencia suficiente para responder sobre una especie, síntoma, plaga, condición de cultivo o recomendación de cuidado.

No se plantea como scraping estático inicial. Se plantea como un proceso controlado, trazable y ejecutado por el agente backend cuando aparece una necesidad real durante el uso del producto.

---

## Objetivo

Permitir que Fotosíntesis AI aprenda de forma progresiva:

- Nuevas especies identificadas.
- Alias regionales.
- Condiciones de cuidado.
- Síntomas y diagnósticos.
- Plagas y enfermedades.
- Recomendaciones de recuperación.
- Información contextual para futuras conversaciones.

---

## Flujo general

```text
Evento de entrada
  ↓
Identificación / síntoma / pregunta
  ↓
Consulta al vector store
  ↓
¿Hay contexto suficiente?
  ├─ Sí
  │   ↓
  │  RAG normal
  │   ↓
  │  Respuesta
  │
  └─ No
      ↓
     Agente ejecuta búsqueda web controlada
      ↓
     Recupera fuentes confiables
      ↓
     Contrasta información
      ↓
     Genera documento estructurado
      ↓
     Guarda documento + metadata + fuentes
      ↓
     Crea embeddings
      ↓
     Reintenta retrieval
      ↓
     Responde al usuario
```

---

## Criterio de activación

El agente podrá activar adquisición incremental cuando ocurra al menos una de estas condiciones:

- La especie no existe en la base vectorial.
- La especie existe, pero no tiene información suficiente sobre el tema consultado.
- El retrieval devuelve resultados con score bajo.
- Hay resultados, pero pertenecen a otra especie.
- La consulta requiere información sobre síntomas, plagas o condiciones no indexadas.
- La respuesta generada no alcanza umbral mínimo de confianza.
- El usuario solicita información local o regional no disponible.

---

## Fuentes confiables

### Fuentes primarias permitidas

- `gbif.org`
- `powo.science.kew.org`
- `plants.ces.ncsu.edu`
- `rhs.org.uk`
- `missouribotanicalgarden.org`

### Fuentes secundarias permitidas

- `wikipedia.org`, solo como fuente auxiliar.
- Sitios educativos o de extensión universitaria.
- APIs botánicas o taxonómicas con documentación pública.

### Fuentes no permitidas por defecto

- Blogs sin autoría clara.
- Tiendas online como fuente principal de cuidado.
- Foros sin moderación.
- Contenido generado por usuarios sin validación.
- Sitios sin fecha, autoría ni trazabilidad.
- Resultados sin URL persistente.

---

## Reglas de adquisición de conocimiento

1. Toda información incorporada debe guardar fuente, URL y fecha de consulta.
2. La información debe estar asociada a una entidad botánica concreta.
3. La taxonomía debe validarse contra una fuente confiable cuando sea posible.
4. La información debe contrastarse con al menos dos fuentes cuando sea posible.
5. Si las fuentes se contradicen, se debe registrar la contradicción.
6. Si la confianza es baja, el sistema debe evitar afirmaciones categóricas.
7. No se debe guardar conocimiento sin trazabilidad.
8. No se debe usar contenido de fuentes no confiables como base única.
9. Los documentos generados automáticamente deben marcarse como `auto_ingested`.
10. Los documentos revisados manualmente podrán marcarse como `reviewed`.
11. Cada documento debe tener un nivel de confianza.
12. El agente debe registrar cuándo activó búsqueda web y por qué.
13. El sistema debe evitar duplicar documentos sobre la misma especie y tema.
14. El sistema debe versionar o actualizar conocimiento si se encuentra información más reciente.
15. La respuesta al usuario debe indicar cuando la información fue incorporada dinámicamente, si es relevante.

---

## Niveles de confianza

### Alta

- Hay coincidencia entre múltiples fuentes confiables.
- La taxonomía está validada.
- No hay contradicciones relevantes.

### Media

- Hay una fuente primaria confiable.
- Hay una fuente secundaria compatible.
- La recomendación es general y segura.

### Baja

- Hay una única fuente confiable.
- Las fuentes tienen contradicciones.
- La información es incompleta o ambigua.

---

## Documento estructurado sugerido

```yaml
document_id:
species_id:
scientific_name:
common_names:
  es:
  es_AR:
  en:
topic:
  - care
  - watering
  - light
  - pests
  - disease
  - recovery
content:
summary:
care:
  light:
  watering:
  soil:
  humidity:
  temperature:
risks:
sources:
  - title:
    url:
    domain:
    source_type:
    retrieved_at:
confidence:
review_status: auto_ingested
created_at:
updated_at:
```

---

## Persistencia

El conocimiento adquirido se debe guardar en dos niveles:

### Base documental

Documento completo, fuente, metadata, estado de revisión y trazabilidad.

### Vector store

Chunks embebidos para recuperación semántica en consultas futuras.

---

## Chunking sugerido

- Chunk por sección semántica.
- Tamaño inicial: 400 a 800 tokens.
- Overlap: 80 a 120 tokens.
- Metadata obligatoria por chunk:
  - `species_id`
  - `scientific_name`
  - `topic`
  - `source_domain`
  - `confidence`
  - `retrieved_at`
  - `review_status`

---

## Requisito OpenSpec

El sistema debe implementar adquisición incremental de conocimiento. Cuando una especie, síntoma, plaga, condición de cultivo o recomendación no tenga suficiente soporte en la base vectorial, el agente backend debe buscar información en fuentes confiables, contrastarla, persistirla como documento estructurado, generar embeddings y reutilizarla mediante RAG en la respuesta actual y en conversaciones futuras.
