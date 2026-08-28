# Laboratorio Estructural Digital — Edificio de Ingeniería

Proyecto del curso de herramientas computacionales en obras civiles.
Modelo estructural 3D en OpenSees + visualización/AR en Unity.

## Estado: Semana 1 completa (benchmark validado contra SAP2000

Deflexión de control del benchmark: **UZ techo bajo G = -0.0635 mm** ✅

---

## Estructura de carpetas

```
proyecto/
├── CLAUDE.md            ← contexto para Claude Code (léelo primero)
├── AGENTS.md            ← bitácora de uso de IA (para la nota)
├── README.md           ← este archivo
│
├── opensees/           ← EL CÁLCULO (Python + OpenSeesPy)
│   ├── benchmark_distribuida.py   → marco validado, carga distribuida
│   ├── generar_json_unity.py      → corre OpenSees y exporta el JSON
│   └── servidor_opensees.py       → servidor Flask (Honors, opcional)
│
├── unity/              ← LA VISUALIZACIÓN (C#)
│   ├── VisorEstructura.cs          → lee JSON y dibuja en Unity
│   ├── AnalizadorEstructural.cs    → conecta con servidor (Honors)
│   └── editor_web_bonus.html       → editor 3D web (bonus, no Unity)
│
├── datos/              ← LA FUENTE DE VERDAD (JSON)
│   └── modelo_unity.json          → nodos, elementos, deformaciones
│
├── planos/             ← DXF reales del edificio (pega aquí tus .dxf)
│
└── docs/               ← guías
    ├── GUIA_unity_paso_a_paso.md   → cómo montar Unity desde cero
    └── GUIA_arquitectura.md        → cómo se conectan las piezas
```

## Por dónde empezar

### 1. Correr el benchmark (verificar que OpenSees funciona)
```bash
cd opensees
pip install openseespy
python benchmark_distribuida.py
```
Debe imprimir equilibrio con error 0.000000 y UZ = -0.0635 mm.

### 2. Generar el JSON para Unity
```bash
python generar_json_unity.py
```
Crea `datos/modelo_unity.json`.

### 3. Ver en Unity
Sigue `docs/GUIA_unity_paso_a_paso.md` (pensada para cero experiencia).
Resumen: crear proyecto 3D, poner el JSON en StreamingAssets, pegar
`VisorEstructura.cs`, Play.

## Regla de oro (no romper)

```
OpenSees CALCULA  →  JSON es la verdad  →  Unity solo MUESTRA
```
Nunca metas cálculo estructural en Unity. Ver CLAUDE.md.

## Reparto del grupo (sugerido)

- **OpenSees / cálculo:** genera modelos y JSON, valida equilibrio.
- **Unity / visual:** toma los JSON y construye el visor + toggles.
- El JSON es el punto de encuentro entre ambos.

## Próximos pasos

- [ ] Edificio completo desde los DXF (planos/)
- [ ] Muros como elementos lineales + diafragmas rígidos
- [ ] Fiber Sections: M-φ, curvas P-M (columna y muro)
- [ ] Unity: toggles (nodos, vigas, ejes, IDs, cargas, deformada)
- [ ] AR (Semana 6)
```
