## ADDED Requirements

### Requirement: Ficha de planta basada en evidencia

El sistema SHALL generar o recuperar una ficha de planta con nombre comun, alias regional, nombre cientifico, descripcion, caracteristicas, condiciones requeridas, cuidados, plagas, enfermedades, recomendaciones y fuentes usadas.

#### Scenario: Ficha con RAG suficiente

- **WHEN** existe evidencia suficiente para la especie en el vector store
- **THEN** el sistema genera la ficha usando contexto recuperado y guarda referencias internas a las fuentes usadas

#### Scenario: Ficha sin evidencia suficiente

- **WHEN** no existe evidencia suficiente para la especie o tema
- **THEN** el sistema activa adquisicion incremental o muestra una ficha parcial indicando limitaciones sin inventar datos botanicos

### Requirement: Alias regional

El sistema SHALL priorizar alias de planta por region, pais o idioma del usuario sin requerir GPS exacto.

#### Scenario: Alias regional disponible

- **WHEN** el usuario tiene region Argentina y existe un alias regional para la especie
- **THEN** la ficha muestra el alias regional como nombre destacado y el nombre cientifico como referencia estable

#### Scenario: Alias regional no disponible

- **WHEN** no existe alias regional para la especie o el usuario no comparte ubicacion
- **THEN** el sistema usa nombre comun general, pais o idioma como fallback y no bloquea la ficha

### Requirement: Acciones contextuales de ficha

La ficha SHALL ofrecer acciones para agregar a Mi Jardin, preguntar al asistente, crear recordatorio y medir luz.

#### Scenario: Usuario agrega planta desde ficha

- **WHEN** el usuario selecciona agregar la planta y confirma nombre o ubicacion del ejemplar
- **THEN** el sistema guarda la planta en Mi Jardin y ofrece crear un recordatorio inicial

### Requirement: Comunicacion de incertidumbre

La ficha MUST indicar cuando la informacion es parcial, adquirida dinamicamente o de confianza baja.

#### Scenario: Fuentes limitadas

- **WHEN** la ficha usa fuentes insuficientes, contradictorias o de confianza baja
- **THEN** el sistema evita afirmaciones categoricas y muestra una advertencia de limitacion
