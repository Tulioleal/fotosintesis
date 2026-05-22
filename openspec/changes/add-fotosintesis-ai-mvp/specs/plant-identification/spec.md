## ADDED Requirements

### Requirement: Captura o carga de imagen
El sistema SHALL permitir tomar una foto o subir una imagen para iniciar una identificacion asistida de planta.

#### Scenario: Imagen valida enviada
- **WHEN** un usuario toma o sube una imagen clara de una planta
- **THEN** el sistema envia la imagen al backend para analisis mediante un proveedor MaaS multimodal agnostico

#### Scenario: Permiso de camara rechazado
- **WHEN** el usuario rechaza el permiso de camara
- **THEN** el sistema explica la limitacion y ofrece subir una imagen desde el dispositivo

### Requirement: Candidatas visuales MaaS
El sistema SHALL devolver y mostrar posibles especies candidatas con nombre comun, nombre cientifico sugerido, rasgos visibles, proveedor y confianza cualitativa.

#### Scenario: MaaS devuelve candidatas
- **WHEN** el proveedor MaaS analiza una imagen usable
- **THEN** el sistema muestra hasta 3 candidatas como posibles coincidencias, incluyendo rasgos visibles y confianza cualitativa alta, media, baja o no concluyente

### Requirement: Identificacion falible y confirmacion obligatoria
El sistema MUST comunicar que la identificacion es asistida y falible, y MUST requerir confirmacion del usuario antes de generar ficha definitiva, guardar en Mi Jardin o crear recordatorios asociados.

#### Scenario: Usuario confirma candidata validada
- **WHEN** el usuario selecciona una candidata taxonomicamente validada
- **THEN** el sistema puede crear o recuperar la ficha de planta y ofrecer agregarla a Mi Jardin

#### Scenario: Baja confianza o resultado no concluyente
- **WHEN** el MaaS devuelve candidatas con confianza baja o no concluyente
- **THEN** el sistema no selecciona una especie automaticamente y pide confirmar entre opciones, tomar otra foto o buscar manualmente

#### Scenario: Usuario rechaza candidatas
- **WHEN** el usuario indica que ninguna candidata coincide con su planta
- **THEN** el sistema permite tomar otra foto o buscar manualmente por nombre

### Requirement: Manejo de fallos de identificacion
El sistema SHALL manejar imagen borrosa, imagen sin planta, MaaS no disponible y ausencia de candidatas utiles con mensajes recuperables.

#### Scenario: Imagen no usable
- **WHEN** la imagen esta borrosa, no contiene una planta o no permite inferencia confiable
- **THEN** el sistema informa el problema y solicita una nueva foto que incluya hojas, tallo o flor si esta disponible
