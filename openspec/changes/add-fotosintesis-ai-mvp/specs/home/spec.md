## ADDED Requirements

### Requirement: Home mobile-first
El sistema SHALL mostrar un Home mobile-first para usuarios autenticados con accesos a identificacion, medidor de luz, recordatorios, Mi Jardin, asistente generativo y busqueda de plantas.

#### Scenario: Home carga acciones principales
- **WHEN** un usuario autenticado abre el Home
- **THEN** el sistema muestra las acciones principales, acceso al asistente, acceso a Mi Jardin y navegacion inferior con seccion activa

### Requirement: Jerarquia visual y navegacion
El Home SHALL priorizar identificar planta como accion primaria y SHALL mantener la identidad visual botanica de Fotosintesis.

#### Scenario: Usuario navega a identificar planta
- **WHEN** el usuario selecciona la accion principal de identificacion
- **THEN** el sistema abre el flujo de camara o carga de imagen

### Requirement: Estados del Home
El Home SHALL incluir estados de loading, error, empty state, reintento y degradacion cuando los datos remotos no carguen.

#### Scenario: Backend no disponible
- **WHEN** el usuario abre el Home y el backend no responde
- **THEN** el sistema muestra la interfaz base, informa que no pudo actualizar datos y permite reintentar

#### Scenario: Usuario nuevo sin datos
- **WHEN** un usuario nuevo abre el Home sin plantas, recordatorios ni conversaciones
- **THEN** el sistema muestra un estado vacio con acciones para identificar, buscar una planta o preguntar al asistente
