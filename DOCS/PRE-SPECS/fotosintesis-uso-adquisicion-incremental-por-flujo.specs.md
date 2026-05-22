# Fotosíntesis AI — Uso de adquisición incremental por flujo

## 1. Después de identificación

### Objetivo

Generar una ficha de planta incluso si la especie no estaba previamente indexada.

### Flujo

```text
  Usuario sube/toma foto
    ↓
  Servicio identifica especies candidatas
    ↓
  Usuario confirma especie
    ↓
  Backend consulta vector store
    ↓
  ¿Existe información suficiente?
    ├─ Sí → genera ficha con RAG
    └─ No
        ↓
      Agente busca información confiable
        ↓
      Contrasta fuentes
        ↓
      Genera documento estructurado
        ↓
      Guarda documento
        ↓
      Crea embeddings
        ↓
      Genera ficha con RAG
```

### Resultado esperado

- Ficha de planta generada.
- Documento persistido.
- Embeddings disponibles para futuras consultas.
- Fuentes registradas.

### Sad paths

- No se encuentra información confiable.
- Hay contradicciones entre fuentes.
- El servicio de búsqueda falla.
- La especie identificada es ambigua.
- El usuario no confirma especie.

---

## 2. Durante “Revivir una planta”

### Objetivo

Completar información faltante sobre síntomas, plagas, enfermedades o recuperación.

### Flujo

```text
Usuario selecciona planta o sube imagen
  ↓
Usuario describe síntomas
  ↓
Agente consulta vector store por especie + síntomas
  ↓
¿Hay evidencia suficiente?
  ├─ Sí → diagnóstico orientativo
  └─ No
      ↓
     Búsqueda controlada sobre especie y síntomas
      ↓
     Contraste de causas probables
      ↓
     Persistencia del conocimiento
      ↓
     Embeddings
      ↓
     Diagnóstico orientativo con nivel de confianza
```

### Resultado esperado

- Hipótesis de causa.
- Pasos de recuperación.
- Nivel de confianza.
- Recomendación de seguimiento.
- Nuevo conocimiento reutilizable.

### Sad paths

- Síntomas insuficientes.
- Imagen no concluyente.
- Planta no identificada.
- Información contradictoria.
- Riesgo de recomendación peligrosa.

---

## 3. Durante el asistente generativo con RAG

### Objetivo

Responder preguntas no cubiertas por la base actual sin inventar información.

### Flujo

```text
Usuario pregunta al asistente
  ↓
Agente interpreta intención
  ↓
Consulta datos de usuario + vector store
  ↓
¿Respuesta soportada por evidencia?
  ├─ Sí → respuesta RAG
  └─ No
      ↓
     Búsqueda web restringida
      ↓
     Validación de fuentes
      ↓
     Generación de documento
      ↓
     Persistencia
      ↓
     Embeddings
      ↓
     Respuesta con nuevo contexto
```

### Resultado esperado

- Respuesta contextualizada.
- Uso de fuentes confiables.
- Persistencia del nuevo conocimiento.
- Reutilización en futuras conversaciones.

### Sad paths

- Pregunta fuera de dominio.
- Pregunta ambigua.
- No hay fuentes confiables.
- Búsqueda lenta o fallida.
- El LLM no responde.
- La herramienta de persistencia falla.

---

## 4. Durante búsqueda manual de plantas

### Objetivo

Permitir que una planta buscada por nombre también pueda activar adquisición incremental.

### Flujo

```text
Usuario busca planta
  ↓
No hay resultado local
  ↓
Agente busca coincidencias confiables
  ↓
Usuario confirma especie
  ↓
Se genera documento y embeddings
  ↓
Se muestra ficha
```

### Resultado esperado

- El usuario puede acceder a información de plantas no indexadas.
- La base crece progresivamente.

---

## 5. Durante alias regionales

### Objetivo

Completar nombres comunes regionales cuando no estén disponibles.

### Flujo

```text
Usuario abre ficha
  ↓
No existe alias para región del usuario
  ↓
Agente busca alias regionales en fuentes confiables
  ↓
Si encuentra evidencia suficiente, guarda alias
  ↓
Muestra alias regional o fallback
```

### Resultado esperado

- Alias localizado cuando exista.
- Fallback claro cuando no haya evidencia.

---

## Regla transversal

La adquisición incremental nunca debe bloquear completamente la experiencia. Si no se puede obtener conocimiento nuevo, el sistema debe responder con la mejor información disponible, indicar limitaciones y ofrecer reintento o búsqueda manual.
