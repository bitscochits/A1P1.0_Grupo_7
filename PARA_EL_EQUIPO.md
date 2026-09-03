# Contexto del proyecto — pégale esto a tu Claude antes de pedirle algo

Grupo 7 · Laboratorio estructural digital · Edificio de Ingeniería UAndes

**Repo:** https://github.com/bitscochits/A1P1.0_Grupo_7
**Ruta local:** `C:\Proyectos\SAP3000` (sin espacios ni tildes: los
scripts de AutoCAD se cortan si la ruta las tiene, y OneDrive pelea con
la carpeta `Library/` de Unity — por eso se sacó de ahí).

> Si vas a trabajar en el código, **primero `git pull`**. El modelo
> cambió fuerte el 1-sep: si tu Claude ve números viejos te va a dar
> respuestas que ya no corresponden.

---

## 1. La regla de oro (esto no se rompe)

```
OpenSees (Python)  →  archivos JSON  →  Unity (visualiza)  →  AR
   CALCULA             fuente de          MUESTRA
                        verdad
```

- **OpenSees calcula.** Todo el análisis estructural sale de Python +
  OpenSeesPy.
- **Los JSON son la fuente de verdad.** La escena de Unity NO lo es.
- **Unity solo visualiza y edita.** No calcula estructura.

**Nunca metas lógica de cálculo estructural en C#.** Si hay que
calcular algo, va en Python y se pasa por JSON.

### Convención de ejes (si el edificio se ve acostado, es esto)

- OpenSees: **Z vertical** (convención ingeniería).
- Unity: **Y vertical** (convención videojuego).
- Conversión: `Unity(x, z_opensees, y_opensees)`. Centralizada en
  `Ejes.AUnity()` — un solo punto, no lo dupliques.

### Unidades

Todo en **m, kN, kPa**.

---

## 2. Cómo está el modelo hoy (números al 1-sep-2026)

| | valor |
|---|---|
| Niveles | 6 (base + 5 pisos), de **3.96 m** cada uno |
| Altura | 19.80 m. Base en cota real **−7.97**, techo en **+11.83** |
| Nodos / elementos | 360 / 694 |
| Elementos de muro | 44 (23 muros, cada uno solo en los pisos donde existe) |
| Diafragmas rígidos | 5 |
| G / Q | 67 067 kN / 11 273 kN |
| Corte basal EX = EY | 6 524 kN |
| Deriva de techo | 1/1288 (EX), 1/1313 (EY) |

Ejes X (8): `8.02, 11.32, 14.72, 18.02, 28.02, 38.02, 48.02, 53.02`
Ejes Y (6): `47.70, 50.26, 55.20, 60.20, 64.65, 72.75`

**Si tu Claude te habla de 8 pisos, 28.5 m, 647 nodos o 1224 elementos,
está usando el modelo viejo.** Ese se corrigió.

### Qué cambió el 1-sep y por qué

1. **Dos ejes Y estaban mal leídos.** `46.92` y `65.22` no salían de
   ningún lado. Resultó que sí existen (son los ejes **3'** y **1b**),
   pero su *globo* —el circulito con la etiqueta en el margen del
   plano— **no está sobre su línea de eje**: cuando dos ejes quedan muy
   juntos, el dibujante corre el globo y lo une con un quiebre. Los
   valores buenos son 47.70 y 64.65.

2. **El edificio no tiene 8 pisos, tiene 5.** Los títulos de las
   plantas dan las cotas directo: −7.97, −4.01, −0.05, +3.91, +7.87,
   +11.83. Pisos de 3.96 m.

3. **Los muros no suben por todos los pisos.** Sobre el nivel ±0.00
   solo queda el núcleo de escalera/ascensor: **13.1 m de los 168.3 m**.
   Los 168.3 m de la fundación incluyen los muros de contención del
   subterráneo, que existen solo bajo tierra. El modelo viejo los
   extruía por toda la altura y daba un edificio **el doble de rígido**
   que el real.

4. **Los muros no pesaban nada.** Faltaba el 8% de la masa. Se detectó
   mirando la deformada exagerada en Unity: los remates del núcleo
   quedaban flotando, clavados a cota real.

---

## 3. Lo que NO hay que tocar sin entender

- **`benchmark_3d.py` es la fuente del modelo del edificio.** Ahí viven
  ejes, alturas, secciones y muros. `modelo_benchmark.py` es la del
  benchmark chico de la Semana 1.
- **El esquema del JSON.** Unity depende de él campo por campo. Si le
  cambias un nombre a una clave, **Unity no da error**: deja el campo en
  su valor por defecto y la deformada sale plana, en silencio.
- **El cruce de inercias en las vigas.** En OpenSees las inercias van
  "cruzadas" en la llamada `element` para elementos horizontales, porque
  con `vecxz=(0,0,1)` el eje local *y* queda vertical. Está comentado en
  el código. No lo "arregles".
- **`heights` y `MUROS` en `benchmark_3d.py`.** Cada muro trae ahora una
  tupla con los pisos en que existe. `verificar_planos.py` la contrasta
  contra el DXF y **falla** si no calza.

### Si quieres borrar algo del modelo

Borrar deja referencias huérfanas, y **algunas no fallan**: si borras
una barra y queda su carga distribuida, OpenSees tira un warning por
consola y **descarta la carga**. El análisis "funciona" con menos carga
de la que crees, y el equilibrio cierra igual porque la carga descartada
nunca entró.

El editor de Unity y el servidor ya limpian/validan esto, pero si editas
Python a mano, revisa que no queden cargas, diafragmas o brazos rígidos
apuntando a algo que ya no existe.

---

## 4. Cómo saber si rompiste algo

```bash
python benchmark_3d.py           # modelo + 4 casos + equilibrio
python export_unity.py           # exporta a Unity + round-trip por el servidor
python verificar_planos.py       # ejes y muros contra los planos DXF
python test_areas_tributarias.py # conservación del reparto de losa
python test_servidor.py          # multi-caso, diafragmas, apoyos
python test_contrato_unity.py    # campos del C# contra el JSON
python benchmark_distribuida.py  # benchmark Semana 1
python generar_json_unity.py     # JSON del benchmark
```

**Los ocho avisan solos si algo se rompió. Córrelos después de
cualquier cambio al modelo.**

Dos referencias externas que no dependen del modelo:

- **Número de oro:** `UZ techo bajo G = −0.06348 mm` en el benchmark de
  la Semana 1, validado contra SAP2000. Si se rompe sin razón, algo está
  mal.
- **Equilibrio:** suma de reacciones = carga aplicada, error < 1e-6.

`verificar_planos.py` necesita los DXF en `C:\dxf_planos\` (están fuera
del repo, pesan 113 MB). Si no los tienes, avisa y no falla.

---

## 5. Trampas que ya nos costaron tiempo

**El equilibrio NO valida el reparto de cargas.** Si a una viga le das
el doble y a la vecina la mitad, la suma de reacciones cierra igual de
bien. Por eso existen los tests de conservación aparte.

**Una verificación que se compara consigo misma no verifica nada.** La
referencia tiene que venir de afuera del modelo.

**Un diafragma rígido NO obliga a que todos los nodos tengan el mismo
`ux`.** El piso se mueve como cuerpo rígido *en su plano*, y con carga
excéntrica **rota**. Confundir esto hace parecer que el diafragma no
funciona cuando sí funciona. Lo que debe cumplirse es
`ux_i = ux_m − rz·(y_i − y_m)`.

**`ops.eleForce()` devuelve fuerzas en ejes GLOBALES**, no locales. Para
leer N/V/M de una barra hay que usar `ops.eleResponse(tag,
'localForce')`. Con vigas que corren en X parecía funcionar por
casualidad.

**`nodeReaction` en un nodo esclavo de un diafragma** devuelve además la
fuerza del vínculo, que es interna. Sumarla al equilibrio hacía fallar
EX por 10 312 kN.

### Unity específicamente

**Los errores de C# están en `unity/Logs/Editor.log`**, no en el diálogo
de Unity. El diálogo muestra el síntoma, no la causa: decía que no
encontraba `CamaraOrbital` cuando el error real estaba en
`EditorEstructura`.

```powershell
Select-String -Path "unity\Logs\Editor.log" -Pattern "error CS" | Select-Object -Last 10
```

**Un solo error de compilación bloquea `Add Component` para todos los
scripts**, aunque el error esté en otro archivo.

**No declares clases con nombres de `UnityEngine`.** Una clase
`Material` propia le gana al `using UnityEngine` y rompe todo
`new Material(...)` del proyecto.

**Unity no vuelca los Player Settings al disco** hasta *File → Save
Project* o un cierre limpio.

**No dupliques clases entre los tres scripts.** Unity no compila si una
clase se declara dos veces:

| archivo | responsabilidad |
|---|---|
| `ModeloEstructural.cs` | **Todas** las clases de datos |
| `VisorEstructura.cs` | Solo dibuja |
| `AnalizadorEstructural.cs` | Solo habla con el servidor |

---

## 6. Si vas a leer los planos DXF

Los DWG se convierten con `accoreconsole.exe` de AutoCAD a una ruta
**sin espacios ni tildes**, y se leen con `ezdxf`. **Unidades del DXF:
centímetros.** Casi todo el dibujo vive dentro de bloques: hay que
explotar los `INSERT` con `virtual_entities()`.

Dos trampas que ya nos costaron una semana:

1. **El globo de un eje no está sobre su eje** cuando hay ejes muy
   juntos. Hay que seguir el quiebre.
2. **Una lámina trae varias plantas, cada una en su propio origen.** No
   se pueden comparar coordenadas crudas entre láminas: hay que
   referenciar cada planta por su grilla (usamos el cruce eje E × eje 3).

`verificar_planos.py` hace las dos cosas.

---

## 7. Qué falta (por si preguntas qué hacer)

1. **Brazos rígidos** en la unión viga-muro. El servidor ya los soporta
   (`brazos_rigidos`); hoy el muro tiene ancho cero ahí.
2. **Empotramiento lateral de la fundación escalonada** — queda fuera
   del modelo a propósito: con diafragma rígido congelaría el piso 1.
3. **Espectro NCh433** — hoy `COEF_SISMICO = 0.10` fijo, sin R, zona ni
   suelo.
4. **Capturas de pantalla** para el informe de la Semana 2 (§6 y §8
   piden mostrar apoyos y viewer *gráficamente* y no hay imágenes).
5. **Fiber Sections** (no lineal, M-φ, P-M) — no empezado.
6. **AR** (Semana 6) — necesitará `python servidor_opensees.py --lan`.

---

## 8. Documentos del repo

| archivo | qué tiene |
|---|---|
| `CLAUDE.md` | contexto técnico permanente — **léelo antes de tocar código** |
| `ESTADO.md` | en qué estábamos, traspaso entre sesiones |
| `reports/semana02.md` | el informe de la entrega |
| `verificar_planos.py` | contrasta el modelo contra los planos |

Si trabajas con Claude Code dentro de la carpeta, `CLAUDE.md` lo lee
solo. Si usas claude.ai en el navegador, pégale este archivo.
