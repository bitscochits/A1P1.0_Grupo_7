# Estado del proyecto — dónde quedamos

Actualizado: 1 de septiembre de 2026, fin de la Semana 2.
Este archivo es el traspaso entre sesiones. El `CLAUDE.md` tiene el
contexto técnico permanente; esto es el "en qué estábamos".

---

## Lo entregado

**Semana 1** — benchmark validado contra SAP2000. Número de oro:
`UZ techo bajo G = −0.06348 mm`. Seis scripts lo verifican solos.

**Semana 2** — `reports/semana02.md`, con los 10 puntos del entregable.
Modelo global del Edificio de Ingeniería: **647 nodos, 1224 elementos,
8 diafragmas rígidos, 23 muros**, cuatro casos de carga (G, Q, EX, EY)
con equilibrio cerrando en todos.

---

## Cómo correr todo

```bash
python benchmark_3d.py           # modelo del edificio + 4 casos + equilibrio
python export_unity.py           # exporta a Unity + round-trip por el servidor
python servidor_opensees.py      # servidor Flask (dejar abierto para Unity)

python test_areas_tributarias.py # conservación y geometría del reparto
python test_servidor.py          # multi-caso, diafragmas, apoyos
python test_contrato_unity.py    # campos del C# contra el JSON
python benchmark_distribuida.py  # benchmark Semana 1
python generar_json_unity.py     # JSON del benchmark
```

Los seis últimos avisan si algo se rompió. **Correrlos después de
cualquier cambio al modelo.**

Unity: `C:\Proyectos\SAP3000\unity`, escena `SampleScene`, ya con
`Visor`, `Analizador`, `Editor` y `Main Camera` cableados. Carga
`modelo_unity_edificio.json`.

---

## Qué se corrigió del modelo del edificio

Todo esto venía de `benchmark_3d.py` (de Pedro) y **ninguno lo detectaba
el chequeo de equilibrio**, porque todos conservaban la carga total.

| problema | qué era | corrección |
|---|---|---|
| `equalDOF(m,s,1,2,6)` | no es diafragma: el piso solo podía trasladarse, nunca rotar | `rigidDiaphragm` + `constraints('Transformation')` |
| cargas puntuales | `F = wL/2` en los nudos: las vigas no flectaban por la losa | `eleLoad -beamUniform` |
| reparto 50/50 | por franjas, igual para viga larga y corta | áreas tributarias a 45° |
| `J = min(Iy,Iz)*0.3` | no es ninguna fórmula; 5.6× a 10.2× bajo | Saint-Venant |
| `F = 10*nivel` | 360 kN de corte basal contra 100.000 kN de peso (0.36%) | `V = 0.10·W` repartido en altura |

---

## Verificado contra los planos

Los DWG se convirtieron a DXF con `accoreconsole.exe` de AutoCAD (ruta
sin espacios, si no el script se corta) y se leyeron con `ezdxf`.
**Unidades del DXF: centímetros.** Los DXF quedaron en `C:\dxf_planos\`.

- **Ejes X:** los 8 del modelo existen todos en `2017_67-100`, al centímetro.
- **Ejes Y:** `46.92` y `65.22` **no existen en ninguna lámina**. Los
  otros cuatro sí. Hay que reemplazarlos o justificarlos.
- **Muros:** 23 muros reales de la capa `RLE-MURO`, 168.3 m acumulados.
  Reemplazaron un supuesto que estaba equivocado. Efecto: la deriva bajo
  EX pasó de 1/348 a **1/2676**.

---

## Pendientes, en orden

1. **Ejes Y 46.92 y 65.22** — no salen de los planos.
2. **Los muros suben por los 8 pisos** — es un supuesto. Las plantas de
   piso (`-101`, `-102`) traen **tres plantas por lámina** y no se pudo
   determinar cuál nivel es cuál. Hay que abrirlas en AutoCAD y leer los
   títulos.
3. **Brazos rígidos** en la unión viga-muro. El servidor ya los soporta
   (`brazos_rigidos`); hoy el muro tiene ancho cero ahí.
4. **Espectro NCh433** — hoy `COEF_SISMICO = 0.10` fijo, sin R, zona ni
   suelo.
5. **Polígono tributario dibujado sobre la losa** — hoy solo se dibuja
   el contorno de la viga seleccionada.
6. **Fiber Sections** (no lineal, M-φ, P-M) — no empezado.
7. **AR** (Semana 6) — necesitará `python servidor_opensees.py --lan`.

---

## Trampas que ya nos costaron tiempo

**Los errores de C# están en `unity/Logs/Editor.log`.** El diálogo de
Unity solo muestra el síntoma: decía que no encontraba `CamaraOrbital`
cuando el error estaba en `EditorEstructura`.

```powershell
Select-String -Path "unity\Logs\Editor.log" -Pattern "error CS" | Select-Object -Last 10
```

**Un solo error de compilación bloquea `Add Component` para todos los
scripts**, aunque el error esté en otro archivo.

**No declarar clases con nombres de `UnityEngine`.** Una clase
`Material` propia le gana al `using UnityEngine` y rompe todo
`new Material(...)` del proyecto. `test_contrato_unity.py` lo verifica.

**Editar C# o Markdown con heredocs rompe los `\n`.** Se convierten en
saltos de línea reales dentro de los strings. Ya pasó tres veces.
Mejor usar la herramienta Edit, o construir el escape con `chr(92)+'n'`.

**Unity no vuelca los Player Settings al disco** hasta *File → Save
Project* o un cierre limpio. `Active Input Handling = Both` hubo que
escribirlo directo en `ProjectSettings.asset` con Unity cerrado.

**El equilibrio no valida el reparto de cargas.** Si a una viga se le da
el doble y a la vecina la mitad, la suma de reacciones cierra igual. Por
eso existen los tests de conservación.

**Un diafragma rígido NO obliga a que todos los nodos tengan el mismo
`ux`.** El piso se mueve como cuerpo rígido *en su plano* y con carga
excéntrica **rota**. Confundir esto hace parecer que el diafragma no
funciona.

---

## Los planos

`Planos edeificio ingeniería/` (fuera del repo, en `.gitignore`):

- `planos_edificio_ing.rar` — **los buenos**, 38 DWG `2017_67-*`
- `02_LT2_ESPECIALIDADES-...zip` — otro proyecto (`2024_22` / LT2), 337 MB

El `.rar` se lee con el `tar` de Windows.
