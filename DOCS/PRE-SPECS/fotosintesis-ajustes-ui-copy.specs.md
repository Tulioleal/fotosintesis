# Fotosíntesis AI — Ajustes en la UI y problemas de copy

## Principio general

El diseño original debe conservarse como identidad visual de la aplicación. El UI kit se usará como una guía flexible, no como un sistema rígido. Se permiten ajustes de espaciado, legibilidad, jerarquía visual, microcopy, contraste y estados de interacción, siempre que la aplicación siga siendo reconocible.

---

## Mantener

- Estética botánica.
- Paleta verde / tierra.
- Cards redondeadas.
- Navegación inferior.
- Uso de imágenes de plantas.
- Sensación mobile-first.
- Identidad visual general de Fotosíntesis.
- Flujos principales existentes.

---

## Ajustar

### Espaciado

- Usar grilla base de 8px.
- Márgenes laterales sugeridos: 16px o 24px.
- Separación entre cards: 12px o 16px.
- Evitar textos pegados a bordes.
- Aumentar padding interno en cards y formularios.

### Jerarquía visual

- Identificar planta debe ser acción primaria.
- Las acciones secundarias deben tener menor peso visual.
- El asistente generativo debe tener acceso visible desde Home.
- Las fichas deben priorizar nombre, especie y acciones principales.

### Legibilidad

- Evitar texto largo sobre imágenes con bajo contraste.
- Usar overlays más consistentes.
- Limitar bloques de texto extensos.
- Dividir contenido en secciones claras.
- Asegurar tamaño mínimo de fuente legible.

### Botones

- Altura mínima sugerida: 44px a 48px.
- CTA principal más evidente.
- Estados: default, hover, active, disabled, loading.
- Texto de acción consistente.

### Formularios

- Labels consistentes.
- Mensajes de error claros.
- Validación visible.
- Estados de foco.
- No depender solo del color para errores.

### Ficha de planta

- Mejorar acordeones.
- Mostrar resumen inicial.
- Agregar CTAs contextuales:
  - Agregar a Mi Jardín.
  - Preguntar al asistente.
  - Crear recordatorio.
  - Medir luz.
- Mostrar alias regional y nombre científico con jerarquía clara.

### Cámara / identificación

- Agregar estados:
  - Cargando cámara.
  - Procesando imagen.
  - Baja confianza.
  - Reintentar.
  - Confirmar especie.
  - Subir imagen como alternativa.

### Medidor de luz

- Explicar que la medición es aproximada si se usa cámara.
- Ofrecer fallback manual.
- Mostrar confiabilidad de la medición.

---

## Problemas de copy detectados

| Texto actual | Problema | Propuesta |
|---|---|---|
| Nombre botanico | Falta tilde | Nombre botánico |
| Plagas y efermedades | Error ortográfico | Plagas y enfermedades |
| ¿Como regarla? | Falta tilde | ¿Cómo regarla? |
| ¿No estas registrado? | Falta tilde | ¿No estás registrado? |
| Registrate | Inconsistencia regional | Registrate / Regístrate, elegir uno |
| Lista recordatorio | Construcción poco natural | Recordatorios |
| Agregar recordatorio | Acción válida, pero puede mejorar | Crear recordatorio |
| Transplantar | Uso menos recomendado | Trasplantar |
| ventada | Error ortográfico | ventana |
| use las manos | Inconsistencia de voseo/tuteo | usá las manos / usa las manos |
| Recordaorio / ecordaorio | Error tipográfico | Recordatorio |
| esten | Falta tilde | estén |
| bridamos | Error ortográfico | brindamos |
| prodrás | Error ortográfico | podrás |

---

## Regla de tono

Elegir una variante y sostenerla en toda la app:

### Opción A — Español neutro

- "Regístrate"
- "Inicia sesión"
- "Usa la cámara"
- "Elige una planta"

### Opción B — Rioplatense

- "Registrate"
- "Iniciá sesión"
- "Usá la cámara"
- "Elegí una planta"

Recomendación actual: usar español rioplatense moderado si el público principal es Argentina. Si se busca una app más regionalizable, usar español neutro.

---

## Microcopy recomendado

### Identificación

- "Tomá una foto clara de la planta."
- "Intentá incluir hojas y tallo."
- "No pudimos identificar la planta con suficiente confianza."
- "Elegí la especie que mejor coincide."

### Ficha

- "También conocida como"
- "Nombre científico"
- "Cuidados recomendados"
- "Condiciones ideales"
- "Plagas y enfermedades frecuentes"

### Recordatorios

- "Crear recordatorio"
- "Elegí una planta"
- "Elegí una acción"
- "La fecha debe ser futura"
- "Recordatorio guardado"

### Medidor de luz

- "La medición por cámara es aproximada."
- "Apuntá la cámara hacia la zona donde está la planta."
- "No tapes la cámara."
- "También podés registrar la luz manualmente."

### Asistente

- "Preguntale al asistente"
- "No tengo suficiente información para afirmarlo con seguridad."
- "Puedo buscar fuentes confiables para completar esta respuesta."
- "Esta recomendación es orientativa."

---

## Criterios de aceptación UI

- La aplicación conserva la identidad visual original.
- Las pantallas son legibles en mobile.
- Todos los formularios muestran estados de error.
- Las acciones principales tienen jerarquía clara.
- El copy no contiene errores ortográficos.
- La navegación inferior indica sección activa.
- Las operaciones lentas tienen estado de carga.
- Las fallas tienen mensajes recuperables.
