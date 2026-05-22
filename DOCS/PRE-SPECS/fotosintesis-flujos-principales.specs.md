# Fotosíntesis AI — Flujos principales

## 1. Autenticación

### Objetivo

Permitir que el usuario cree una cuenta, inicie sesión y recupere acceso.

### Flujo happy path

```text
Abrir aplicación
  ↓
Pantalla de bienvenida
  ↓
Registrarse / Iniciar sesión
  ↓
Validación de credenciales
  ↓
Home
```

### Casos contemplados

- Registro con email y contraseña.
- Inicio de sesión con credenciales existentes.
- Recuperación de contraseña.
- Login social, si se decide implementar.

### Sad paths

- Email inválido.
- Contraseña incorrecta.
- Campos obligatorios vacíos.
- Cuenta ya existente.
- Backend no disponible.

---

## 2. Home

### Objetivo

Concentrar las acciones principales de la aplicación.

### Accesos principales

- Identificar planta.
- Medidor de luz.
- Recordatorios.
- Mi Jardín.
- Asistente generativo.
- Búsqueda de plantas.

### Flujo happy path

```text
Usuario autenticado
  ↓
Home
  ↓
Selecciona acción principal
  ↓
Navega al flujo correspondiente
```

### Sad paths

- Fallo al cargar datos del usuario.
- Error al cargar próximas tareas.
- Sin conexión.
- Estado vacío para usuario nuevo.

---

## 3. Identificación de plantas

### Objetivo

Identificar una planta desde una imagen de forma asistida, mostrando candidatas probables generadas por un MaaS multimodal, validando taxonomía con GBIF y solicitando confirmación del usuario antes de generar una ficha contextualizada.

### Flujo happy path

```text
Home
  ↓
Identificar planta
  ↓
Tomar foto / subir imagen
  ↓
MaaS multimodal analiza imagen
  ↓
Devuelve top 3 candidatas + rasgos visibles + confianza cualitativa
  ↓
Backend valida nombres científicos con GBIF
  ↓
Usuario confirma especie
  ↓
Backend consulta vector store
  ↓
¿Hay información suficiente?
  ├─ Sí → genera ficha con RAG
  └─ No → adquisición incremental de conocimiento
  ↓
Ficha de planta
  ↓
Agregar a Mi Jardín
```

### Datos mínimos

- Imagen.
- Candidatas de especie.
- Nivel de confianza cualitativo.
- Rasgos visibles usados por el modelo.
- Nombre científico validado, si GBIF lo confirma.
- Alias regional, si existe.
- Fuentes de conocimiento utilizadas.

### Reglas

- La identificación debe presentarse como “posibles coincidencias”.
- El sistema no debe tratar la salida del MaaS como identificación definitiva.
- La ficha final requiere confirmación del usuario.
- Si GBIF no valida el nombre científico, la candidata debe marcarse como no validada o descartarse.

### Sad paths

- Usuario no concede permiso de cámara.
- Imagen borrosa.
- Imagen sin planta.
- MaaS multimodal no disponible.
- GBIF no valida las candidatas.
- Baja confianza en las candidatas.
- Usuario no confirma ninguna especie.
- No hay información suficiente y la búsqueda incremental falla.

---

## 4. Ficha de planta

### Objetivo

Presentar información clara y accionable sobre una especie.

### Contenido

- Nombre común.
- Alias regional.
- Nombre científico.
- Descripción.
- Características.
- Condiciones requeridas.
- Guía de cuidados.
- Plagas y enfermedades.
- Acciones: agregar a Mi Jardín, preguntar al asistente, crear recordatorio, medir luz.

### Flujo happy path

```text
Abrir ficha
  ↓
Mostrar identidad de la planta
  ↓
Mostrar secciones de información
  ↓
Usuario expande secciones o ejecuta acción
```

### Sad paths

- Información parcial.
- Fuentes insuficientes.
- Error al generar resumen.
- Planta duplicada en Mi Jardín.

---

## 5. Mi Jardín

### Objetivo

Permitir que el usuario gestione sus plantas guardadas.

### Flujo happy path

```text
Home
  ↓
Mi Jardín
  ↓
Lista de plantas guardadas
  ↓
Seleccionar planta
  ↓
Detalle / historial / recordatorios
```

### Funciones

- Listar plantas.
- Buscar dentro del jardín.
- Ver próximo cuidado.
- Acceder a la ficha.
- Eliminar planta.
- Crear recordatorio asociado.

### Sad paths

- Jardín vacío.
- Búsqueda sin resultados.
- Error al sincronizar plantas.
- Eliminación de planta con recordatorios activos.

---

## 6. Asistente generativo con RAG

### Objetivo

Responder preguntas sobre plantas usando información contextual, RAG y herramientas.

### Flujo happy path

```text
Usuario pregunta
  ↓
Agente interpreta intención
  ↓
Consulta datos del usuario y vector store
  ↓
¿Hay evidencia suficiente?
  ├─ Sí → responde con RAG
  └─ No → adquisición incremental de conocimiento
  ↓
Respuesta contextualizada
```

### Herramientas posibles

- Consultar vector store.
- Consultar Mi Jardín.
- Buscar fuentes confiables.
- Persistir conocimiento.
- Crear recordatorios.
- Consultar mediciones de luz.

### Sad paths

- Pregunta ambigua.
- Pregunta fuera de dominio.
- Retrieval insuficiente.
- Fallo del proveedor LLM.
- Prompt malicioso.
- Herramienta no disponible.

---

## 7. Revivir una planta

### Objetivo

Ayudar al usuario a diagnosticar problemas y recuperar plantas deterioradas.

### Flujo happy path

```text
Usuario abre "Revivir una planta"
  ↓
Selecciona planta o sube imagen
  ↓
Describe síntomas
  ↓
Agente consulta RAG
  ↓
¿Hay evidencia suficiente?
  ├─ Sí → diagnóstico orientativo
  └─ No → adquisición incremental de conocimiento
  ↓
Causas probables + pasos de recuperación + seguimiento
```

### Entradas

- Planta guardada o especie candidata.
- Imagen opcional.
- Síntomas.
- Historial de riego, luz o recordatorios, si existe.

### Sad paths

- Síntomas insuficientes.
- Imagen no usable.
- Diagnóstico contradictorio.
- Información insuficiente.
- Solicitudes riesgosas o no recomendables.

---

## 8. Recordatorios

### Objetivo

Gestionar acciones de cuidado recurrentes o puntuales.

### Flujo happy path

```text
Home / Ficha / Asistente
  ↓
Crear recordatorio
  ↓
Seleccionar planta, acción, fecha, hora y repetición
  ↓
Guardar
  ↓
Mostrar en lista de recordatorios
```

### Funciones

- Crear.
- Editar.
- Eliminar.
- Marcar como completado.
- Generar próxima ocurrencia.
- Sugerir recordatorios con IA.

### Sad paths

- Fecha en el pasado.
- Planta no seleccionada.
- Acción no seleccionada.
- Repetición inválida.
- Permisos de notificación rechazados.
- Error de persistencia.

---

## 9. Medidor de luz

### Objetivo

Registrar o estimar condiciones de luz para contextualizar recomendaciones.

### Flujo happy path

```text
Home / Ficha
  ↓
Medidor de luz
  ↓
Permiso de cámara o sensor
  ↓
Medición
  ↓
Clasificación: baja / media / alta / directa
  ↓
Asociar medición a una planta
```

### Fuentes posibles

- Cámara desde browser.
- AmbientLightSensor si el navegador lo soporta.
- Registro manual como fallback.

### Sad paths

- Permiso de cámara rechazado.
- Sensor no soportado.
- Medición poco confiable.
- Imagen sobreexpuesta u obstruida.
- Usuario cancela el flujo.
