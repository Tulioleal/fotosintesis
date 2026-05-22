# Fotosíntesis AI — Resultado esperado

## Resultado del producto

Fotosíntesis AI debe funcionar como una aplicación mobile-first para asistir la identificación de plantas mediante MaaS multimodal, guardarlas en un jardín personal y asistir al usuario en su cuidado mediante IA generativa.

El producto no debe ser solo un clasificador de plantas. La identificación visual es el punto de entrada, pero se comunicará como asistida y falible. El núcleo del sistema es el asistente generativo con RAG, agentes y adquisición incremental de conocimiento.

---

## Resultado para el usuario

El usuario debe poder:

- Obtener posibles coincidencias de una planta a partir de una imagen.
- Confirmar manualmente la especie más probable antes de generar la ficha final.
- Consultar una ficha clara y accionable.
- Guardar la planta en Mi Jardín.
- Recibir recomendaciones de cuidado.
- Crear o aceptar recordatorios sugeridos.
- Preguntar al asistente sobre riego, luz, suelo, plagas o síntomas.
- Intentar recuperar una planta deteriorada con guía orientativa.
- Medir o registrar luz ambiental.
- Obtener respuestas con limitaciones claras cuando no haya suficiente evidencia.

---

## Resultado técnico

El sistema debe incluir:

- Frontend mobile-first usable.
- Backend FastAPI.
- LLM como componente generativo central.
- RAG con vector store.
- Agente con herramientas.
- Adquisición incremental de conocimiento.
- Persistencia de documentos, embeddings y metadata.
- Tests unitarios, de integración y end-to-end.
- Métricas, logs y observabilidad.
- Docker Compose.
- Kubernetes / GKE.
- Documento de evaluación.

---

## Resultado académico

El proyecto debe demostrar:

- Uso real de IA generativa.
- Resolución de un problema concreto.
- Integración end-to-end.
- Evaluación seria de respuestas generadas.
- Uso de al menos tres componentes avanzados.
- Producto usable por usuarios reales.
- Despliegue reproducible local y cloud.

---

## Criterios de éxito

### Producto

- El flujo principal de identificación asistida funciona con MaaS multimodal, validación GBIF y confirmación del usuario.
- El usuario puede guardar una planta solo después de confirmar la especie.
- El asistente responde preguntas contextualizadas.
- El sistema puede crear recordatorios.
- El diagnóstico de planta deteriorada entrega hipótesis y pasos razonables.
- La app mantiene identidad visual reconocible.

### RAG

- El sistema recupera información relevante.
- Las respuestas se apoyan en evidencia.
- El sistema evita inventar cuando no hay contexto.
- El conocimiento nuevo puede reutilizarse en futuras conversaciones.

### Agente

- El agente decide cuándo usar herramientas.
- El agente puede activar búsqueda controlada.
- El agente puede persistir nuevo conocimiento.
- El agente puede crear recordatorios cuando corresponde.

### Adquisición incremental

- La búsqueda se restringe a fuentes confiables.
- La información se contrasta.
- La metadata se guarda.
- Los embeddings se generan.
- El conocimiento queda disponible para RAG.

### Evaluación

- Existe dataset de prueba.
- Se ejecutan métricas automáticas.
- Se ejecuta LLM-as-a-judge.
- Se documentan resultados, errores y limitaciones.

### Infraestructura

- El stack local levanta con Docker Compose.
- El sistema tiene manifiestos o Helm charts para Kubernetes/GKE.
- El README permite reproducir el proyecto.
- Los tests pasan en verde.

---

## Definición final

Fotosíntesis AI debe presentarse como un asistente inteligente de jardinería doméstica que combina identificación visual, recuperación aumentada, adquisición dinámica de conocimiento y asistencia generativa para mejorar el cuidado cotidiano de plantas.
