## ADDED Requirements

### Requirement: Medicion de luz con prioridad tecnica

El sistema SHALL estimar o registrar luz ambiental usando esta prioridad: AmbientLightSensor, camara como fallback y registro manual como fallback final.

#### Scenario: Sensor de luz disponible

- **WHEN** el browser soporta AmbientLightSensor y el usuario concede permiso
- **THEN** el sistema usa iluminancia en lux y muestra una lectura clasificada

#### Scenario: Fallback por camara

- **WHEN** no hay AmbientLightSensor disponible pero la camara puede usarse
- **THEN** el sistema estima luz por luminancia de imagen y comunica que la medicion es aproximada

#### Scenario: Registro manual

- **WHEN** no hay sensor ni camara usable o el usuario rechaza permisos
- **THEN** el sistema permite registrar manualmente baja, media, alta o directa

### Requirement: Clasificacion y confiabilidad

El sistema SHALL clasificar mediciones como baja, media, alta o directa y SHALL registrar confiabilidad de la medicion.

#### Scenario: Medicion poco confiable

- **WHEN** la camara esta tapada, sobreexpuesta o la medicion es inconsistente
- **THEN** el sistema marca la medicion como no confiable y pide repetirla con instrucciones

### Requirement: Asociacion a plantas

El sistema SHALL permitir asociar mediciones de luz a una planta guardada para contextualizar recomendaciones futuras.

#### Scenario: Medicion asociada

- **WHEN** el usuario guarda una medicion y selecciona una planta de Mi Jardin
- **THEN** el sistema persiste la medicion asociada a esa planta y la deja disponible para el asistente
