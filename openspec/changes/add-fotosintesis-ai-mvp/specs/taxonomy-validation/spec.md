## ADDED Requirements

### Requirement: Validacion taxonomica GBIF
El sistema SHALL validar nombres cientificos candidatos contra GBIF Species API antes de usarlos para fichas, Mi Jardin, recordatorios o conocimiento persistente.

#### Scenario: Candidata validada
- **WHEN** GBIF normaliza correctamente el nombre cientifico de una candidata
- **THEN** el sistema guarda el identificador estable, taxonomia normalizada, genero, familia, especie y sinonimos relevantes

#### Scenario: Candidata no validada
- **WHEN** GBIF no puede validar el nombre cientifico de una candidata
- **THEN** el sistema marca la candidata como no validada o la descarta, y no genera ficha definitiva a partir de ella

### Requirement: Resolucion de sinonimos
El sistema SHALL resolver sinonimos taxonomicos cuando GBIF indique un nombre aceptado distinto al nombre candidato.

#### Scenario: GBIF devuelve nombre aceptado
- **WHEN** una candidata coincide con un sinonimo en GBIF
- **THEN** el sistema usa el nombre aceptado como referencia estable y conserva el sinonimo como metadata

### Requirement: Independencia de APIs botanicas especializadas
El sistema MUST funcionar sin depender obligatoriamente de APIs botanicas especializadas externas para validar identificaciones.

#### Scenario: API botanica especializada no configurada
- **WHEN** no existe una API botanica especializada disponible
- **THEN** el sistema continua usando MaaS multimodal para candidatas y GBIF para validacion taxonomica
