## ADDED Requirements

### Requirement: Gestion de recordatorios
El sistema SHALL permitir crear, editar, eliminar, listar y completar recordatorios de cuidado asociados a una planta guardada o contexto confirmado.

#### Scenario: Recordatorio manual exitoso
- **WHEN** el usuario selecciona planta, accion, fecha, hora y repeticion validas
- **THEN** el sistema guarda el recordatorio y lo muestra en la lista de recordatorios

#### Scenario: Formulario invalido
- **WHEN** el usuario intenta guardar un recordatorio sin planta, sin accion, con fecha pasada, hora vacia o repeticion invalida
- **THEN** el sistema impide guardar y muestra el mensaje de validacion correspondiente

### Requirement: Recordatorios sugeridos por IA
El sistema SHALL poder sugerir recordatorios segun especie, cuidado recomendado, ficha, Mi Jardin o conversacion con el asistente, y MUST requerir confirmacion del usuario antes de crearlos.

#### Scenario: Usuario acepta sugerencia inicial
- **WHEN** el sistema sugiere un recordatorio de riego para una planta agregada a Mi Jardin y el usuario confirma
- **THEN** el sistema crea el recordatorio con frecuencia sugerida y guarda la justificacion

### Requirement: Recurrencia y completado
El sistema SHALL registrar completados y calcular proxima ocurrencia para recordatorios recurrentes.

#### Scenario: Completar recordatorio recurrente
- **WHEN** el usuario marca como completado un recordatorio recurrente pendiente
- **THEN** el sistema registra la accion y calcula la siguiente ocurrencia

### Requirement: Permisos de notificacion
El sistema SHALL guardar recordatorios aunque el usuario rechace permisos de notificacion y SHALL informar la limitacion.

#### Scenario: Permiso rechazado
- **WHEN** el usuario rechaza permisos de notificacion
- **THEN** el recordatorio queda guardado y el sistema informa que no podra enviar notificaciones push
