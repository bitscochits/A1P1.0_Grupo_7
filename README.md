# Laboratorio Estructural Digital — Edificio de Ingeniería

Proyecto del curso de herramientas computacionales en obras civiles.
Modelo estructural 3D en OpenSees + visualización/AR en Unity.

## Estado: Semana 1 completa (benchmark validado contra SAP2000)

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

---

# Edificio LT2 — modelo desde los planos de cálculo

Segundo edificio del proyecto, armado **entero desde los planos DWG**
`2024_22`. Va **separado** del edificio vecino: la lámina 700 rotula
`JUNTA DE DILATACIÓN 10 cm` y habla de `2ª ETAPA` / `ETAPA ANTERIOR`, así que
al unir los dos modelos **no comparten nodos**.

## Abrir el visor

```powershell
.\ver.ps1
```

Corre el modelo, resuelve el caso G, escribe `data/modelo_unity.json`, lo copia
al visor y lo abre. Opciones:

| | |
|---|---|
| `.\ver.ps1 -SoloExportar` | solo escribe el JSON |
| `.\ver.ps1 -Servidor` | además levanta el servidor de reanálisis en vivo |
| `.\ver.ps1 -Recompilar` | fuerza recompilar la app de Unity (~10 min) |

`ver.ps1` busca un Python con `openseespy`: primero `.venv` de este repo, si no
el de `P1L2_Grupo_7`. Para crear el propio: `.\setup.ps1`.

> **El paso de copiar el JSON no es opcional.** El visor lee
> `StreamingAssets/modelo_unity.json`; si no se copia muestra el modelo viejo
> **sin avisar de nada**.

## El pipeline

```
DWG ──► DXF ──► geometria_lt2_2024_22.json ──► modelo OpenSees ──► modelo_unity.json ──► Unity
   dwg_a_dxf.ps1    src/planos/                 src/modelo_lt2.py   src/exportar_unity.py
```

| Archivo | Qué hace |
|---|---|
| `src/planos/` | ingestor de planos (ver su propio README) |
| `src/modelo_lt2.py` | modelo OpenSees: nodos, elementos, diafragmas, cargas |
| `src/malla.py` | de ejes dibujados a una malla conectada |
| `src/panos.py` | paños de losa y áreas tributarias a 45° |
| `src/exportar_unity.py` | contrato JSON hacia el visor |
| `src/lanzar_unity.py` | compila y abre el visor |
| `verificar_lt2.py` | 30 verificaciones numéricas del modelo |
| `test_planos.py` | 51 tests del ingestor |
| `tests/test_contrato_unity.py` | campos C# contra claves del JSON |

## Estado

| | |
|---|---|
| Nodos · columnas · muros · vigas · brazos | 372 · 43 · 76 · 307 · 90 |
| Carga total (G) | 34 914 kN |
| Error de equilibrio | 1.6 × 10⁻⁷ kN |
| Hormigón | G35_10, f'c = 35 MPa |
| Cargas plantas tipo | G = 6.30 · Q = 4.90 kN/m² (lámina 700) |

Detalle completo y limitaciones: `reports/modelo_lt2.md`.
