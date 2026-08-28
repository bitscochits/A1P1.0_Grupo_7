# AGENTS.md — Registro de uso de agentes de IA

> Este archivo documenta cómo el grupo usa agentes de IA (OpenCode,
> Claude Code) en el proyecto. Es parte de la evaluación del curso.
> Mantener actualizado semana a semana.

---

## Agentes en uso

| Agente | Para qué | Quién |
|---|---|---|
| OpenCode | (definir) | (nombre) |
| Claude Code | desarrollo de código, edición local | (nombre) |

## Criterios de aceptación (generales)

Todo cambio importante generado por IA debe cumplir:

1. **Verificación numérica.** Comparar contra un valor conocido.
   Ej: el benchmark da UZ techo = -0.0635 mm bajo G. Si un cambio
   rompe esto sin razón, se rechaza.
2. **Equilibrio.** Suma de reacciones = carga aplicada, error < 1e-6.
3. **No romper la arquitectura.** OpenSees calcula, Unity muestra.
4. **Código entendible.** Cualquier integrante debe poder explicar
   qué hace (la nota evalúa comprensión individual).
5. **Sin cambios al esquema JSON** sin acuerdo del grupo.

## Ciclo de trabajo

```
Issue → Plan → Build → Test → Review → Merge
```

- **Issue:** describir la tarea con criterio de aceptación claro.
- **Plan:** el agente propone cómo lo hará.
- **Build:** el agente escribe el código.
- **Test:** verificar (equilibrio, valor de control, que compile).
- **Review:** un humano lee y entiende el código.
- **Merge:** integrar al proyecto.

## Ejemplo de buen encargo a un agente

> "Implementar la lectura de tributary_areas.json. No modificar el
> esquema. Verificar que la suma de cargas transferidas sea igual a
> q*A dentro de tolerancia 1e-10."

## Ejemplo de mal encargo

> "Haz la herramienta de áreas tributarias." (vago, sin criterio)

---

## Registro semanal

### Semana 1
- **Tarea:** benchmark 3D OpenSees + verificación.
- **IA usada:** (describir qué se pidió y a qué agente).
- **Verificación:** benchmark validado contra SAP2000, UZ = -0.0635 mm,
  diferencia 0.4%. Equilibrio error 0.000000.
- **Aprendizaje:** (qué entendió el grupo / qué revisó críticamente).

### Semana 2
- **Tarea:** (pendiente)
- ...

### Semana 3
- ...

---

## Verificaciones críticas del proyecto

| Qué | Valor esperado | Cómo se verifica |
|---|---|---|
| Deflexión benchmark G | UZ = -0.0635 mm | correr benchmark, leer nodo techo |
| Equilibrio G | error < 1e-6 | suma reacciones vs carga aplicada |
| Sección L área | 0.2375 m² | fórmula geométrica |
| Sección L I gravedad | 4.628e-3 m⁴ | composición de rectángulos |

## Notas de revisión crítica de IA

> Aquí el grupo anota cuándo la IA se equivocó y cómo se detectó.
> Esto es valioso para la nota (demuestra verificación crítica).

- Ejemplo: "El agente leyó el momento en el índice equivocado de
  eleForce (M3 en vez de M2). Se detectó porque salía 0. Corregido."
