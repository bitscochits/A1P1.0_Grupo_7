# Estado del proyecto — dónde quedamos

Actualizado: 1 de septiembre de 2026, fin de la Semana 2.
Este archivo es el traspaso entre sesiones. El `CLAUDE.md` tiene el
contexto técnico permanente; esto es el "en qué estábamos".

---

## Lo entregado

**Semana 1** — benchmark validado contra SAP2000. Número de oro:
`UZ techo bajo G = −0.06348 mm`. Seis scripts lo verifican solos.

**Semana 2** — `reports/semana02.md`, con los 10 puntos del entregable.
Modelo global del Edificio de Ingeniería, ya con la geometría verificada
contra los planos: **360 nodos, 694 elementos, 5 diafragmas rígidos,
23 muros que suben solo hasta donde los muestran las plantas**, cuatro
casos de carga (G, Q, EX, EY) con equilibrio cerrando en todos.

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
python verificar_planos.py       # modelo contra los DXF (ejes y muros)
```

Los siete últimos avisan si algo se rompió. **Correrlos después de
cualquier cambio al modelo.**

`verificar_planos.py` necesita los DXF en `C:\dxf_planos\`; si no están,
avisa y no falla.

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

Todo esto lo rehace `python verificar_planos.py`.

- **Ejes X:** los 8 del modelo existen todos en `2017_67-100`, al centímetro.
- **Ejes Y:** los 6 existen. `46.92` y `65.22` estaban mal leídos
  (ver abajo); corregidos a **47.70** (eje 3') y **64.65** (eje 1b).
- **Muros:** 23 muros reales de la capa `RLE-MURO`, 168.3 m acumulados.
  Pero ese es el largo **en la fundación**; hacia arriba se van cortando.

### Los globos de eje engañan: hay que seguir el quiebre

Un eje se identifica por su **globo** (un `CIRCLE` de r=0.438 m en el
margen, con la etiqueta `MTEXT` adentro). Cuando dos ejes quedan más
cerca que un diámetro —y acá hay pares a 0.25 m— el dibujante **corre el
globo** y lo une a su eje con un **quiebre**: un tramo corto horizontal
y luego uno vertical hasta la línea larga.

Leer la altura del globo da entonces la coordenada equivocada. Eso fue
exactamente lo que pasó:

| eje | globo | eje real | |
|---|---|---|---|
| **3'** | 46.925 | **47.701** | quiebre de 0.78 m |
| 3 | 47.951 | 47.951 | directo |
| 2a | 50.256 | 50.256 | directo |
| 2 | 55.201 | 55.201 | directo |
| 1'' | 60.201 | 60.201 | directo |
| 1 | 63.117 | 64.101 | quiebre |
| 1' | 64.154 | 64.351 | quiebre |
| 1AA | 65.851 | 64.626 | quiebre |
| **1b** | 65.221 | **64.651** | quiebre de 0.57 m |
| 8 | 72.751 | 72.751 | directo |

Tres verificaciones independientes de que los corregidos son los buenos:

1. La grilla **relativa al eje 3** es idéntica en las cuatro láminas de
   planta (`0, 2.305, 7.250, 12.250, 16.150 m`), aunque cada una está
   insertada en un origen distinto.
2. Los muros de `RLE-MURO` caen sobre los ejes corregidos: el muro del
   eje 3-3' ocupa la banda `Y 47.60–47.90` (contiene 47.701, **no**
   46.92) y el del eje 1b la banda `64.55–64.85` (contiene 64.651, **no**
   65.22).
3. Las elevaciones se titulan **«ELEVACION EJE 3-3'»** y
   **«ELEVACION EJE 1-1'»**: los ejes van de a pares porque son las dos
   caras del mismo muro.

Efecto de esta corrección **por sí sola**, antes de tocar la altura: la
planta se acortó de 25.83 a 25.05 m en Y, G pasó de 100254 a 97779 kN y
Q de 18598 a 18036 kN. Los totales finales están más abajo.

### El edificio tiene 5 pisos de 3.96 m, no 8 de 3.5 m

Los títulos de las plantas (`RLA-TEXTOS2`) y las cotas de losa que los
acompañan:

| lámina | planta | losa |
|---|---|---|
| `-100` | Planta fundaciones | −7.97 |
| `-101` | Planta cielo 1° subterráneo | **−4.01** |
| `-101` | Planta cielo piso 1° | **−0.05** |
| `-102` | Planta cielo piso 2° | **+3.91** |
| `-102` | Planta cielo piso 3° | **+7.87** |
| `-103` | Planta cielo piso 4° | **+11.83** |

Son **dos** plantas por lámina, no tres. Espaciamiento uniforme de
**3.96 m**, confirmado por las marcas de nivel de la elevación
`2017_67-300` (13.79, 17.75, 21.71, 25.67, 29.63, 33.59 → 3.96 exacto)
y por sus rótulos de piso: `1°S, 1°, 2°, 3°, 4°`. Las láminas `-2xx` son
armaduras que referencian estas mismas plantas; no hay pisos 5° a 8°.

### Los muros NO suben por los pisos

Cada planta se llevó al sistema de la fundación con su propio datum
(cruce eje E × eje 3). Que muros idénticos caigan en coordenadas
idénticas desde tres orígenes de inserción distintos es la prueba de que
la traslación está bien.

| | Fundac. | 1° subt | piso 1° | piso 2° | piso 3° | piso 4° |
|---|---|---|---|---|---|---|
| largo presente (m) | 168.3 | 105.0 | 78.8 | **13.1** | **13.1** | **13.1** |
| % de los 168.3 m | 100% | 62% | 47% | **8%** | **8%** | **8%** |

Sobre el nivel ±0.00 sobrevive **solo el núcleo de escalera/ascensor**
(≈3.7 × 10 m, entre los ejes Ea–Ed y 2a–1''): las mismas 12 corridas,
idénticas en los pisos 2°, 3° y 4°.

Los 168.3 m incluyen los **muros de contención del subterráneo**
(`2017_67-002` trae «disposición de armaduras en muro contención»), que
existen solo bajo tierra. Irónicamente, el supuesto viejo que se
descartó —«4 muros de 3.3 m en un núcleo poniente»— era casi el núcleo
real de los pisos altos.

---

## El modelo v2: la geometría real

Con lo anterior verificado, el modelo se rehízo a los 5 pisos reales.

| | antes (v1) | ahora (v2) |
|---|---|---|
| niveles | 9 (base + 8) | **6** (base + 5) |
| altura de piso | 4.0 m y luego 3.5 | **3.96 m**, uniforme |
| altura total | 28.50 m | **19.80 m** (techo en +11.83) |
| nodos | 647 | **360** |
| elementos | 1224 | **694** |
| elementos de muro | 184 | **44** |
| diafragmas | 8 | **5** |
| G total | 100254 kN | **67067 kN** (5359 son peso propio de muros) |
| Q total | 18598 kN | **11273 kN** |
| corte basal EX/EY | 9965 kN | **6524 kN** |
| deriva de techo EX | 1/2676 | **1/1288** |
| deriva de techo EY | — | **1/1313** |

Muro por piso, ahora que cada uno sube solo hasta donde lo muestran las
plantas: **105.0 / 84.6 / 13.3 / 13.3 / 13.3 m**.

La deriva pasó de 1/2676 a 1/1288: el edificio real es del orden del
doble de flexible que lo que decía el modelo, porque los muros de
contención ya no suben por toda la altura. Sigue siendo la deriva de un
edificio con núcleo de muros, no la de un marco desnudo.

`COTA_BASE = -7.97` guarda la cota real de la base; la cota de un nivel
es `COTA_BASE + heights[lev]`.

### Los ocho muros del oriente y el apoyo escalonado

Ocho muros aparecen recién en el piso 2°: el subterráneo no llega hasta
allá y su zapata queda más alta. Se apoyan en el nivel 1, no en la base.

Ahí hay una trampa que costó un rato. Ese nodo **ya es esclavo del
diafragma** del piso 1. Empotrarlo del todo ata también `ux, uy, rz` y,
como el diafragma es rígido, **deja inmóvil el piso entero**: la deriva
del piso 1 se iría a cero y los 105 m de muro de ese piso quedarían de
adorno. Se restringen entonces solo los DOF que el diafragma no toca
(`uz, rx, ry`), el mismo recurso que se usa con los nodos maestros.

Ese apoyo toma bajo G la mitad del peso propio del primer tramo de esos
muros (1504.01 kN entre los ocho) y 0.00 kN bajo Q, EX y EY: sostiene el
muro y nada más. Lo que sí queda fuera del modelo es el empotramiento
**lateral** de esa fundación escalonada.

### Los muros no pesaban nada

Lo delató la deformada exagerada en Unity: los 5 remates del núcleo
quedaban clavados a cota real, flotando sobre un techo que bajaba a su
alrededor. La causa: `apply_gravity` cargaba losa, vigas y columnas — a
los nodos de muro no les llegaba ninguna carga vertical, y tampoco
estaban en `peso_sismico`. Faltaba el 8% de la masa (5359 kN).

Corregido con el mismo esquema de las columnas (mitad a cada extremo de
cada tramo), en G, en el peso sísmico y en el JSON para Unity. Ahora el
núcleo baja 0.20 mm contra 2.4 mm del techo: sigue casi quieto, pero
porque un muro es ~12× más rígido a carga axial que el marco a flexión,
no porque no pese. El round-trip del export ahora **aborta** si la suma
de reacciones no calza con lo aplicado (antes solo imprimía).

Segunda trampa, en el chequeo de equilibrio: `nodeReaction` en un nodo
que es esclavo de un diafragma devuelve además la **fuerza del vínculo**,
que es interna. Sumarla hacía fallar EX por 10312 kN y EY por 3421 kN.
En horizontal solo suman los apoyos que tienen `ux/uy` restringidos.
Con eso los cuatro casos cierran con error < 3e-4 kN, y el round-trip
por el servidor reproduce los mismos totales.

---

## Pendientes, en orden

1. ~~Ejes Y 46.92 y 65.22~~ — **resuelto**: eran los ejes 3' y 1b, mal
   leídos por el quiebre del globo. Corregidos a 47.70 y 64.65.
2. ~~Los muros suben por los 8 pisos~~ — **resuelto y corregido**: no
   suben, y el edificio no tiene 8 pisos. El modelo se rehízo a la
   geometría real (ver «El modelo v2» abajo).
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

**El globo de un eje no está sobre su eje.** Si dos ejes quedan a menos
de un diámetro de globo, el dibujante corre el globo y lo une con un
quiebre. Leer la altura del globo dio dos ejes fantasma (46.92 y 65.22)
que costaron una semana de «esto no sale de los planos». Hay que seguir
el quiebre: `verificar_planos.py` lo hace.

**Una lámina de planta trae más de una planta, cada una con su propio
origen de inserción.** Para comparar entre niveles hay que referenciar
cada planta por su grilla (acá, el cruce eje E × eje 3), nunca por las
coordenadas crudas del DXF.

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
