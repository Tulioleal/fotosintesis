## ADDED Requirements

### Requirement: Activacion por evidencia insuficiente

El sistema SHALL activar adquisicion incremental cuando una especie, sintoma, plaga, condicion de cultivo, alias regional o recomendacion no tenga suficiente soporte en la base vectorial.

#### Scenario: Especie no indexada despues de identificacion

- **WHEN** el usuario confirma una especie validada y el vector store no tiene informacion suficiente
- **THEN** el agente busca informacion confiable, la contrasta, persiste un documento estructurado, crea embeddings y genera la ficha usando RAG

#### Scenario: Pregunta no cubierta por el corpus

- **WHEN** el usuario pregunta al asistente y el retrieval devuelve score bajo, documentos de otra especie o contexto insuficiente
- **THEN** el agente puede iniciar busqueda web restringida antes de responder

### Requirement: Fuentes confiables y restricciones

El sistema MUST restringir adquisicion a fuentes confiables o explicitamente validadas y MUST evitar usar fuentes no confiables como base unica.

#### Scenario: Fuente permitida

- **WHEN** el agente encuentra informacion en dominios como `gbif.org`, `powo.science.kew.org`, `plants.ces.ncsu.edu`, `rhs.org.uk` o `missouribotanicalgarden.org`
- **THEN** el sistema puede usarla como fuente primaria y guardar dominio, URL y fecha de consulta

#### Scenario: Fuente no confiable

- **WHEN** la unica informacion disponible proviene de blogs sin autoria clara, tiendas online, foros sin moderacion o contenido sin URL persistente
- **THEN** el sistema no la usa como base unica para conocimiento persistente

### Requirement: Documento estructurado y trazabilidad

El sistema SHALL guardar conocimiento adquirido como documento estructurado con especie, nombres comunes, topicos, contenido, riesgos, fuentes, confianza, estado de revision y timestamps.

#### Scenario: Persistencia exitosa

- **WHEN** el agente incorpora conocimiento nuevo
- **THEN** el sistema guarda documento, fuentes, metadata, `review_status` auto_ingested, nivel de confianza y razon de activacion

### Requirement: Chunking, embeddings y reutilizacion

El sistema SHALL dividir documentos en chunks semanticos, crear embeddings y permitir retrieval futuro con filtros por especie, tema, fuente, confianza y fecha.

#### Scenario: Nuevo conocimiento reutilizado

- **WHEN** un usuario consulta luego sobre una especie o tema previamente adquirido
- **THEN** el RAG recupera los chunks persistidos y los usa como contexto

### Requirement: Degradacion controlada

La adquisicion incremental MUST NOT bloquear completamente la experiencia si falla.

#### Scenario: Busqueda incremental falla

- **WHEN** no se encuentran fuentes confiables o falla la persistencia
- **THEN** el sistema responde con la mejor informacion disponible, indica limitaciones y ofrece reintento o busqueda manual
