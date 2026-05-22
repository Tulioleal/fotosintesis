## ADDED Requirements

### Requirement: Guardar plantas confirmadas

El sistema SHALL permitir guardar en Mi Jardin solo plantas con especie confirmada por el usuario y taxonomia validada cuando corresponda.

#### Scenario: Guardado exitoso

- **WHEN** el usuario confirma una especie validada y selecciona agregar a Mi Jardin
- **THEN** el sistema crea una planta guardada asociada al usuario, ficha, imagen opcional y datos personalizados

#### Scenario: Intento sin confirmacion

- **WHEN** el usuario intenta guardar una candidata no confirmada
- **THEN** el sistema bloquea la accion y solicita confirmar una especie primero

### Requirement: Listado y busqueda en Mi Jardin

El sistema SHALL permitir listar, buscar y abrir el detalle de plantas guardadas.

#### Scenario: Jardin con plantas

- **WHEN** el usuario abre Mi Jardin y tiene plantas guardadas
- **THEN** el sistema muestra una lista con nombre, imagen si existe y proximo cuidado si existe

#### Scenario: Jardin vacio

- **WHEN** el usuario abre Mi Jardin sin plantas guardadas
- **THEN** el sistema muestra un estado vacio con acciones para identificar o buscar una planta

#### Scenario: Busqueda local

- **WHEN** el usuario busca una planta por nombre dentro de Mi Jardin
- **THEN** el sistema filtra la lista por coincidencia y conserva acceso al detalle

### Requirement: Eliminacion de plantas

El sistema SHALL permitir eliminar plantas guardadas con confirmacion explicita cuando existan recordatorios activos.

#### Scenario: Eliminacion con recordatorios activos

- **WHEN** el usuario intenta eliminar una planta con recordatorios activos
- **THEN** el sistema advierte que los recordatorios se eliminaran o desactivaran y solicita confirmacion explicita

### Requirement: Contexto de cuidado del jardin

Mi Jardin SHALL conservar relaciones con recordatorios, mediciones de luz, conversaciones e historial relevante para contextualizar recomendaciones.

#### Scenario: Asistente consulta jardin

- **WHEN** el usuario pregunta por una planta guardada
- **THEN** el asistente puede consultar Mi Jardin para adaptar la respuesta al contexto del usuario
