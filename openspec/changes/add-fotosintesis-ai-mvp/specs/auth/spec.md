## ADDED Requirements

### Requirement: Registro de usuario

El sistema SHALL permitir crear una cuenta con nombre, email y contrasena validos.

#### Scenario: Registro exitoso

- **WHEN** un usuario completa nombre, email y contrasena validos y confirma el registro
- **THEN** el sistema crea la cuenta, inicia la sesion y navega al Home

#### Scenario: Registro invalido

- **WHEN** un usuario intenta registrarse con campos obligatorios vacios, email invalido, contrasena menor a 8 caracteres o email ya registrado
- **THEN** el sistema impide el registro y muestra un mensaje de error recuperable junto al formulario

### Requirement: Inicio de sesion

El sistema SHALL permitir iniciar sesion con credenciales validas y SHALL rechazar credenciales invalidas sin revelar si el email existe.

#### Scenario: Login exitoso

- **WHEN** un usuario existente ingresa email y contrasena validos
- **THEN** el sistema autentica al usuario, crea una sesion y muestra el Home con su saludo

#### Scenario: Login fallido

- **WHEN** un usuario ingresa email inexistente, contrasena incorrecta, email con formato invalido o campos vacios
- **THEN** el sistema rechaza el acceso y muestra un mensaje claro sin exponer informacion sensible

### Requirement: Recuperacion de acceso

El sistema SHALL permitir iniciar un flujo de recuperacion de contrasena desde la pantalla de autenticacion.

#### Scenario: Solicitud de recuperacion

- **WHEN** un usuario solicita recuperar acceso con un email en formato valido
- **THEN** el sistema inicia el flujo de recuperacion y muestra una confirmacion neutral

### Requirement: Proteccion de flujos autenticados

El sistema SHALL requerir sesion autenticada para acceder a Home, identificacion, Mi Jardin, recordatorios, medidor de luz y asistente.

#### Scenario: Usuario no autenticado intenta acceder a flujo privado

- **WHEN** una request o navegacion intenta acceder a un flujo privado sin sesion valida
- **THEN** el sistema redirige a autenticacion o responde acceso no autorizado segun corresponda
