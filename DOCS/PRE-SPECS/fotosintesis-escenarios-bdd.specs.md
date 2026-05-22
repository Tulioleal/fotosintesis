# Fotosíntesis AI — Escenarios BDD

```gherkin
# language: es
```

## Característica: Autenticación

```gherkin
Característica: Autenticación

  Escenario: Usuario nuevo ve la bienvenida
    Dado que el usuario abre la aplicación por primera vez
    Cuando la pantalla inicial termina de cargar
    Entonces debe ver el logo de Fotosíntesis
    Y debe ver las acciones "Iniciar sesión" y "Registrarse"

  Escenario: Usuario se registra correctamente
    Dado que el usuario está en la pantalla de registro
    Cuando completa nombre, apellido, correo electrónico y contraseña válidos
    Y confirma el registro
    Entonces el sistema debe crear la cuenta
    Y debe mostrar la pantalla Home

  Esquema del escenario: Registro inválido
    Dado que el usuario está en la pantalla de registro
    Cuando completa el formulario con "<caso_invalido>"
    Y confirma el registro
    Entonces el sistema debe impedir el registro
    Y debe mostrar el mensaje "<mensaje>"

    Ejemplos:
      | caso_invalido              | mensaje                                        |
      | correo inválido            | Ingresá un correo electrónico válido            |
      | contraseña corta           | La contraseña debe tener al menos 8 caracteres |
      | campos obligatorios vacíos | Completá los campos obligatorios                |
      | correo ya registrado       | Ya existe una cuenta con este correo            |

  Escenario: Usuario inicia sesión correctamente
    Dado que el usuario tiene una cuenta existente
    Cuando ingresa correo y contraseña válidos
    Entonces debe acceder al Home
    Y el sistema debe mostrar su nombre en el saludo

  Esquema del escenario: Inicio de sesión fallido
    Dado que el usuario está en la pantalla de inicio de sesión
    Cuando intenta iniciar sesión con "<credenciales>"
    Entonces el sistema debe rechazar el acceso
    Y debe mostrar "<mensaje>"

    Ejemplos:
      | credenciales            | mensaje                              |
      | contraseña incorrecta   | Correo o contraseña incorrectos      |
      | correo inexistente      | Correo o contraseña incorrectos      |
      | correo con formato malo | Ingresá un correo electrónico válido |
      | campos vacíos           | Completá correo y contraseña         |
```

---

## Característica: Home

```gherkin
Característica: Home y navegación principal

  Antecedentes:
    Dado que el usuario inició sesión correctamente

  Escenario: Home carga acciones principales
    Cuando el usuario ingresa al Home
    Entonces debe ver la búsqueda
    Y debe ver las acciones "Identificar", "Medidor de luz" y "Recordatorio"
    Y debe ver acceso a "Mi Jardín"
    Y debe ver acceso al asistente

  Escenario: Usuario navega a identificar planta
    Dado que el usuario está en el Home
    Cuando selecciona "Identificar"
    Entonces el sistema debe abrir el flujo de cámara o carga de imagen

  Escenario: Home no puede cargar datos remotos
    Dado que el usuario está autenticado
    Y el backend no responde
    Cuando el usuario abre el Home
    Entonces el sistema debe mostrar la interfaz base
    Y debe informar que no se pudieron actualizar los datos
    Y debe permitir reintentar
```

---

## Característica: Búsqueda y alias regional

```gherkin
Característica: Búsqueda y alias localizado de plantas

  Antecedentes:
    Dado que el usuario inició sesión correctamente

  Escenario: Usuario busca una planta por nombre común
    Dado que el usuario está en el Home
    Cuando busca "pata de oso"
    Entonces el sistema debe mostrar resultados relacionados
    Y cada resultado debe incluir nombre común y nombre científico

  Escenario: Usuario ve alias localizado por región
    Dado que el usuario tiene región "Argentina"
    Y existe un alias regional para la especie identificada
    Cuando abre la ficha de la planta
    Entonces debe ver el alias regional como nombre destacado
    Y debe ver el nombre científico como referencia estable

  Escenario: Usuario no comparte ubicación
    Dado que el usuario no otorgó permisos de ubicación
    Cuando abre una ficha de planta
    Entonces el sistema debe usar idioma o país del perfil como fallback
    Y no debe bloquear el uso de la aplicación

  Escenario: No existen alias regionales para la planta
    Dado que la planta no tiene alias regional registrado
    Cuando el usuario abre la ficha
    Entonces el sistema debe mostrar el nombre común general
    Y debe ocultar la sección de alias regionales si no hay datos
```

---

## Característica: Identificación

```gherkin
Característica: Identificación de planta por imagen

  Antecedentes:
    Dado que el usuario inició sesión correctamente

  Escenario: Usuario identifica una planta con foto válida mediante MaaS
    Dado que el usuario abre el flujo de identificación
    Cuando toma o sube una foto clara de una planta
    Entonces el sistema debe enviar la imagen al proveedor MaaS multimodal
    Y debe recibir posibles especies candidatas
    Y cada candidata debe mostrar nombre, rasgos visibles y nivel de confianza cualitativo

  Escenario: Candidatas del MaaS son validadas taxonómicamente
    Dado que el MaaS devolvió especies candidatas
    Cuando el backend procesa las candidatas
    Entonces debe validar los nombres científicos contra GBIF
    Y debe marcar como válidas solo las candidatas normalizadas correctamente

  Escenario: Usuario confirma una especie candidata
    Dado que el sistema mostró especies candidatas validadas
    Cuando el usuario selecciona una especie
    Entonces el sistema debe crear o recuperar la ficha de la especie
    Y debe generar un resumen de cuidado con RAG
    Y debe ofrecer "Agregar a Mi Jardín"

  Escenario: Planta identificada sin información previa en la base
    Dado que el usuario identificó y confirmó una especie
    Y la especie no tiene información suficiente en el vector store
    Cuando el sistema intenta generar la ficha de planta
    Entonces el agente debe buscar información en fuentes confiables
    Y debe contrastar la información recuperada
    Y debe guardar un documento estructurado con fuentes y fecha de consulta
    Y debe crear embeddings del documento
    Y debe generar la ficha usando RAG

  Escenario: Identificación con baja confianza
    Dado que el usuario sube una imagen ambigua
    Cuando el MaaS devuelve candidatas con confianza baja o no concluyente
    Entonces el sistema no debe seleccionar una especie automáticamente
    Y debe mostrar el resultado como posibles coincidencias
    Y debe pedir al usuario confirmar entre varias opciones o tomar otra foto

  Escenario: Usuario no concede permiso de cámara
    Dado que el usuario abre el flujo de cámara
    Cuando rechaza el permiso de cámara
    Entonces el sistema debe explicar que necesita acceso a cámara
    Y debe ofrecer subir una imagen desde el dispositivo

  Escenario: GBIF no valida ninguna candidata
    Dado que el MaaS devolvió candidatas para una imagen
    Cuando GBIF no puede validar sus nombres científicos
    Entonces el sistema no debe generar una ficha definitiva
    Y debe pedir otra foto o permitir búsqueda manual

  Escenario: Usuario no confirma ninguna candidata
    Dado que el sistema mostró posibles coincidencias
    Cuando el usuario indica que ninguna coincide con su planta
    Entonces el sistema debe permitir tomar otra foto
    Y debe permitir buscar manualmente por nombre
```

---

## Característica: Ficha de planta

```gherkin
Característica: Ficha de planta

  Antecedentes:
    Dado que el usuario abrió una ficha de planta válida

  Escenario: Usuario consulta información general de la planta
    Cuando la ficha termina de cargar
    Entonces debe mostrar nombre común, nombre científico y alias disponibles
    Y debe mostrar descripción, características, condiciones requeridas, guía de cuidados y plagas

  Escenario: Ficha generada con evidencia RAG suficiente
    Dado que existe información curada para la especie
    Cuando el sistema genera la guía de cuidado
    Entonces la respuesta debe usar documentos recuperados
    Y debe evitar datos no soportados por el corpus
    Y debe guardar referencias internas a las fuentes usadas

  Escenario: Ficha sin evidencia suficiente
    Dado que no hay suficiente información en la base de conocimiento
    Cuando el sistema intenta generar la guía
    Entonces debe mostrar una ficha parcial
    Y debe indicar que la información disponible es limitada
    Y no debe inventar condiciones de cuidado

  Escenario: Usuario agrega la planta a Mi Jardín
    Dado que el usuario está en una ficha de planta
    Cuando selecciona "Agregar planta"
    Y confirma nombre o ubicación de la planta
    Entonces el sistema debe guardar la planta en Mi Jardín
    Y debe ofrecer crear un recordatorio inicial

  Escenario: Usuario intenta agregar una planta duplicada
    Dado que la planta ya existe en Mi Jardín
    Cuando selecciona "Agregar planta"
    Entonces el sistema debe advertir que ya está guardada
    Y debe permitir agregar otro ejemplar o cancelar
```

---

## Característica: Mi Jardín

```gherkin
Característica: Mi Jardín

  Antecedentes:
    Dado que el usuario inició sesión correctamente

  Escenario: Usuario ve sus plantas guardadas
    Dado que el usuario tiene plantas en Mi Jardín
    Cuando abre "Mi Jardín"
    Entonces debe ver una lista de plantas
    Y cada planta debe mostrar nombre, imagen y próximo cuidado si existe

  Escenario: Mi Jardín está vacío
    Dado que el usuario no tiene plantas guardadas
    Cuando abre "Mi Jardín"
    Entonces debe ver un estado vacío
    Y debe ver acciones para identificar o buscar una planta

  Escenario: Usuario busca dentro de Mi Jardín
    Dado que el usuario tiene varias plantas guardadas
    Cuando busca una planta por nombre
    Entonces la lista debe filtrarse por coincidencia
    Y debe conservar acceso al detalle de cada planta

  Escenario: Usuario elimina una planta con recordatorios activos
    Dado que una planta guardada tiene recordatorios activos
    Cuando el usuario decide eliminarla
    Entonces el sistema debe advertir que se eliminarán o desactivarán sus recordatorios
    Y debe pedir confirmación explícita
```

---

## Característica: Asistente generativo

```gherkin
Característica: Asistente generativo con RAG y herramientas

  Antecedentes:
    Dado que el usuario inició sesión correctamente

  Escenario: Usuario pregunta sobre una planta guardada
    Dado que el usuario tiene "Pata de oso" en Mi Jardín
    Cuando pregunta "¿Cada cuánto tengo que regarla?"
    Entonces el asistente debe recuperar contexto de la especie
    Y debe responder con una recomendación concreta
    Y debe adaptar la respuesta a la información disponible del usuario

  Escenario: Asistente adquiere conocimiento durante una conversación
    Dado que el usuario pregunta al asistente sobre una planta
    Y el retrieval no devuelve contexto suficiente
    Cuando el agente detecta falta de evidencia
    Entonces debe ejecutar una búsqueda web restringida a fuentes confiables
    Y debe validar la información recuperada contra al menos una fuente adicional cuando sea posible
    Y debe persistir el conocimiento con metadata de fuentes
    Y debe crear embeddings
    Y debe responder usando el nuevo contexto recuperado

  Escenario: Usuario pregunta algo ambiguo
    Dado que el usuario tiene varias plantas guardadas
    Cuando pregunta "¿La tengo que regar hoy?"
    Entonces el asistente debe pedir aclaración sobre qué planta
    Y no debe asumir una planta sin contexto suficiente

  Escenario: El RAG no encuentra evidencia suficiente
    Dado que el usuario pregunta algo específico
    Y la base de conocimiento no contiene información suficiente
    Cuando el asistente genera la respuesta
    Entonces debe explicar que no tiene suficiente evidencia
    Y debe ofrecer una recomendación general segura
    Y no debe inventar datos botánicos

  Escenario: Usuario pide crear un recordatorio desde el chat
    Dado que el usuario conversa con el asistente sobre una planta
    Cuando dice "Recordame regarla todos los lunes"
    Entonces el agente debe detectar la intención de crear recordatorio
    Y debe pedir confirmación si faltan datos
    Y al confirmar debe crear el recordatorio

  Escenario: Prompt malicioso intenta ignorar reglas del sistema
    Dado que el usuario envía una instrucción para ignorar fuentes o políticas internas
    Cuando el asistente procesa el mensaje
    Entonces debe mantener las reglas del sistema
    Y debe responder solo con información permitida y relevante
```

---

## Característica: Revivir una planta

```gherkin
Característica: Diagnóstico para revivir una planta

  Antecedentes:
    Dado que el usuario inició sesión correctamente

  Escenario: Usuario consulta si puede revivir una planta con síntomas suficientes
    Dado que el usuario abre "¿Puedo revivir una planta?"
    Cuando indica síntomas como hojas blandas, tallo débil y suelo húmedo
    Entonces el sistema debe generar causas probables
    Y debe proponer pasos de recuperación
    Y debe sugerir seguimiento en próximos días

  Escenario: Diagnóstico requiere información no indexada
    Dado que el usuario consulta cómo revivir una planta
    Y el sistema conoce la especie o una especie candidata
    Y la base vectorial no contiene información suficiente sobre los síntomas indicados
    Cuando el agente procesa el diagnóstico
    Entonces debe buscar información confiable sobre la especie y los síntomas
    Y debe contrastar causas probables entre fuentes
    Y debe guardar el nuevo conocimiento como documento trazable
    Y debe crear embeddings para futuras consultas
    Y debe responder con un diagnóstico orientativo y nivel de confianza

  Escenario: Usuario da síntomas insuficientes
    Dado que el usuario abre el flujo de diagnóstico
    Cuando escribe "mi planta está mal"
    Entonces el sistema debe pedir más información
    Y debe sugerir preguntas sobre riego, luz, suelo, manchas, plagas y temperatura

  Escenario: Diagnóstico no concluyente
    Dado que el sistema recibe síntomas contradictorios
    Cuando genera el diagnóstico
    Entonces debe mostrar varias hipótesis ordenadas por probabilidad
    Y debe sugerir acciones de bajo riesgo
    Y debe recomendar seguimiento
```

---

## Característica: Recordatorios

```gherkin
Característica: Recordatorios de cuidado

  Antecedentes:
    Dado que el usuario inició sesión correctamente

  Escenario: Usuario crea un recordatorio manual
    Dado que el usuario abre "Nuevo recordatorio"
    Cuando selecciona planta, acción, fecha, hora y repetición
    Entonces el sistema debe guardar el recordatorio
    Y debe mostrarlo en la lista de recordatorios

  Escenario: Usuario crea un recordatorio sugerido por IA
    Dado que el usuario agregó una planta a Mi Jardín
    Y el sistema conoce la frecuencia de riego recomendada
    Cuando el sistema sugiere un recordatorio inicial
    Y el usuario confirma
    Entonces debe crearse un recordatorio con esa frecuencia
    Y debe guardarse la justificación de la sugerencia

  Esquema del escenario: Formulario de recordatorio inválido
    Dado que el usuario está creando un recordatorio
    Cuando completa el formulario con "<problema>"
    Entonces el sistema debe impedir guardar
    Y debe mostrar "<mensaje>"

    Ejemplos:
      | problema            | mensaje                     |
      | sin planta          | Elegí una planta            |
      | sin acción          | Elegí una acción            |
      | fecha en el pasado  | Elegí una fecha futura      |
      | hora vacía          | Elegí una hora              |
      | repetición inválida | Elegí una frecuencia válida |

  Escenario: Usuario marca un recordatorio como completado
    Dado que existe un recordatorio pendiente para hoy
    Cuando el usuario lo marca como completado
    Entonces el sistema debe registrar la acción
    Y debe calcular la próxima ocurrencia si es recurrente

  Escenario: Usuario no concede permisos de notificación
    Dado que el sistema solicita permisos de notificación
    Cuando el usuario los rechaza
    Entonces el recordatorio debe guardarse igual
    Y el sistema debe informar que no podrá enviar notificaciones push
```

---

## Característica: Medidor de luz

```gherkin
Característica: Medidor de luz

  Antecedentes:
    Dado que el usuario inició sesión correctamente

  Escenario: Usuario mide luz usando cámara
    Dado que el usuario abre el medidor de luz
    Cuando concede permiso de cámara
    Y apunta la cámara hacia la fuente de luz cercana a la planta
    Entonces el sistema debe estimar el nivel de luz
    Y debe clasificarlo como baja, media, alta o directa
    Y debe permitir asociar la medición a una planta

  Escenario: Browser soporta AmbientLightSensor
    Dado que el dispositivo soporta AmbientLightSensor
    Y el usuario concede permiso al sensor
    Cuando inicia la medición
    Entonces el sistema debe usar el valor de iluminancia en lux
    Y debe mostrar una lectura más precisa

  Escenario: Usuario rechaza permiso de cámara
    Dado que el usuario abre el medidor de luz
    Cuando rechaza el permiso de cámara
    Entonces el sistema debe mostrar una alternativa manual
    Y debe permitir elegir nivel de luz sin medición automática

  Escenario: Browser no soporta medición automática
    Dado que el browser no soporta cámara utilizable ni sensor de luz
    Cuando el usuario abre el medidor
    Entonces el sistema debe mostrar un mensaje de incompatibilidad
    Y debe ofrecer registro manual de luz

  Escenario: Medición de luz poco confiable
    Dado que el usuario inicia una medición
    Cuando la imagen está tapada o sobreexpuesta
    Entonces el sistema debe marcar la medición como no confiable
    Y debe pedir repetir la medición siguiendo las instrucciones
```

---

## Característica: Calidad, evaluación y observabilidad

```gherkin
Característica: Calidad, evaluación y observabilidad

  Escenario: Backend expone health check
    Dado que el backend está desplegado
    Cuando se consulta el endpoint de health check
    Entonces debe responder estado saludable
    Y debe indicar si LLM, base de datos y vector store están disponibles

  Escenario: Backend expone métricas básicas
    Dado que el usuario realiza una consulta al asistente
    Cuando la request finaliza
    Entonces el sistema debe registrar latencia, estado, tokens usados y errores si existen

  Escenario: Evaluación automática de respuestas generadas
    Dado que existe un dataset de preguntas de prueba
    Cuando se ejecuta el pipeline de evaluación
    Entonces el sistema debe calcular métricas automáticas apropiadas
    Y debe ejecutar evaluación LLM-as-a-judge
    Y debe guardar resultados y análisis

  Escenario: Respuesta generada no cumple umbral de calidad
    Dado que el pipeline de evaluación tiene umbrales definidos
    Cuando una respuesta obtiene score menor al umbral mínimo
    Entonces el sistema debe marcar el caso como fallido
    Y debe dejar evidencia para análisis

  Escenario: Error del LLM durante inferencia
    Dado que el usuario consulta al asistente
    Y el proveedor LLM no responde
    Cuando vence el timeout configurado
    Entonces el sistema debe mostrar un mensaje recuperable
    Y debe registrar el error
    Y no debe perder el mensaje del usuario
```
