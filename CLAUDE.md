# CLAUDE.md — Contexto del proyecto

> **RUTA DEL PROYECTO: `C:\Proyectos\SAP3000`**
> Se movió aquí desde OneDrive el 1-sep-2026. OneDrive y Unity se
> llevan mal: `Library/` son 40.000 archivos que cambian constantemente
> y OneDrive los sincronizaba mientras Unity los escribía. La ruta
> además ya no tiene espacios ni tildes, que rompían los scripts de
> AutoCAD.
>
> **Repo:** https://github.com/bitscochits/A1P1.0_Grupo_7 (público)
> Colaboradores: `ppcastillo1-oss` (admin), `monsecubi` (write).

---

## EL REPO SE REORDENO (3-sep-2026) -- leelo antes de tocar rutas

Este archivo mas abajo describe el proyecto cuando todo vivia en la raiz.
**Ya no.** El repo esta partido por edificio, y una carpeta tiene un dueno.

```
edificios/ingenieria/   el cuerpo antiguo  (planos 2017_67)
edificios/lt2/          el cuerpo nuevo    (planos 2024_22)
edificios/conjunto/     los dos unidos por la junta de dilatacion
comun/                  rutas.py, contrato.py, calcular.py,
                        servidor_opensees.py, lanzar_unity.py
benchmark/              modelo_benchmark.py y el benchmark de Semana 1
data/geometria|modelo|resultados|unity/
```

Los dos edificios resultaron ser **el mismo en dos etapas**: comparten
las seis cotas de piso (-7.97 a +11.83) y los 3.96 m de altura, y los
separa la junta de dilatacion en x = 42.75.

### Donde quedo cada archivo que este documento nombra

| dice mas abajo | esta en |
|---|---|
| `benchmark_3d.py` | `edificios/ingenieria/benchmark_3d.py` |
| `export_unity.py` | `edificios/ingenieria/export_unity.py` |
| `verificar_planos.py` | `edificios/ingenieria/verificar_planos.py` |
| `modelo_benchmark.py` | `benchmark/modelo_benchmark.py` |
| `generar_json_unity.py` | `benchmark/generar_json_unity.py` |
| `test_areas_tributarias.py` | `benchmark/test_areas_tributarias.py` |
| `servidor_opensees.py` | `comun/servidor_opensees.py` |
| `modelo_unity.json` (benchmark) | `data/unity/benchmark.json` |
| `modelo_unity_edificio.json` | `data/unity/ingenieria.json` |

### El pipeline de cuatro etapas

```
planos DXF -> data/geometria/<ed>.json -> data/modelo/<ed>.json
           -> data/resultados/<ed>_<caso>.json -> data/unity/<ed>.json
```

`data/modelo/` es el contrato neutro y el punto donde se unen los dos
edificios. `comun/calcular.py` no sabe de que edificio se trata: resuelve
cualquiera. Su motor es `construir_y_resolver()` del servidor, la misma
funcion del reanalisis desde Unity.

### Nunca mas contar dirname

`comun/rutas.py` es el unico archivo que sabe donde esta cada cosa, y
encuentra la raiz SUBIENDO hasta la marca del repo. Contar
`os.path.dirname` a mano falla en silencio cuando un archivo cambia de
carpeta: escribe el JSON un nivel mas arriba y el sintoma aparece mucho
despues, en Unity, como un modelo que "no se actualiza".

### Trampa al verificar equilibrio

`nodeReaction` en un nodo atado por un diafragma devuelve tambien la
fuerza de esa restriccion, que es INTERNA. Sumar todas las filas de
`reacciones` da el corte basal al doble o al triple. Pero tampoco se
pueden descartar esos nodos enteros: los arranques de muro escalonados
son apoyos verticales de verdad. La separacion correcta es POR GRADO DE
LIBERTAD -- esta implementada y comentada en `comun/calcular.py`.

**Todo lo demas de este documento sigue vigente**: la regla de oro, el
swap de ejes, el cruce de inercias, eleResponse vs eleForce, las trampas
de JsonUtility y de los globos de eje en los DXF.

---

# CLAUDE.md â€” Contexto del proyecto

> Este archivo le da contexto a Claude Code (y a cualquier agente de IA)
> sobre el proyecto. LÃ©elo antes de trabajar en cualquier tarea.

---

## QuÃ© es este proyecto

Laboratorio estructural digital del **Edificio de IngenierÃ­a** de la
Universidad de los Andes, para un curso de "herramientas computacionales
en obras civiles". Es un proyecto grupal (3 estudiantes), de 7 semanas.

**El objetivo NO es un videojuego.** Es construir y verificar un modelo
estructural real y una interfaz para interrogarlo, modificarlo y
entenderlo.

## Arquitectura (regla de oro)

Hay una separaciÃ³n estricta que NO se debe romper:

```
OpenSees (Python)  â†’  archivos JSON  â†’  Unity (visualiza)  â†’  AR
   CALCULA              fuente de          MUESTRA
                        verdad
```

- **OpenSees calcula.** Todo el anÃ¡lisis estructural (desplazamientos,
  reacciones, fuerzas, curvas) sale de Python + OpenSeesPy.
- **Los JSON son la fuente de verdad.** La geometrÃ­a y resultados viven
  en JSON, independientes de Unity. La escena Unity NO es la fuente de
  verdad del modelo.
- **Unity solo visualiza y edita.** No calcula estructura. Lee JSON y
  dibuja. Puede ayudar a crear/editar datos, pero el cÃ¡lculo vuelve a
  OpenSees.

**Nunca metas lÃ³gica de cÃ¡lculo estructural en C#/Unity.** Si algo hay
que calcularlo, va en Python/OpenSees y se pasa por JSON.

## ConvenciÃ³n crÃ­tica de ejes

- **OpenSees:** Z es vertical (convenciÃ³n ingenierÃ­a).
- **Unity:** Y es vertical (convenciÃ³n videojuego).
- **ConversiÃ³n:** `Unity(x, z_opensees, y_opensees)`.
  La altura (z de OpenSees) va a la Y de Unity.

Si el edificio se ve "acostado" en Unity, este swap estÃ¡ mal.

## Unidades

- Todo en **m, kN, kPa** (consistente).
- Para SAP2000 se usa **N, m** â†’ multiplicar fuerzas por 1000.
- MÃ³dulo elÃ¡stico: `Ec = 4700*sqrt(fpc)*1000` (fpc en MPa â†’ kPa).

## Estado actual del proyecto (Semana 1 COMPLETA)

### Benchmark validado âœ…
Un marco 3D de prueba: **4 columnas + 4 vigas L**, un piso, 4x4x3 m.
- Columnas: cuadradas 30x30 cm.
- Vigas: secciÃ³n **L** que representa losa colaborante (NO se modelan
  losas con elementos finitos; se idealizan como vigas L).
- Material: hormigÃ³n **G-25** (fpc = 25 MPa, Ec = 23.500 MPa).

**Resultado validado contra SAP2000:**
- DeflexiÃ³n vertical nodo techo bajo carga G: **UZ = -0.0635 mm**.
- SAP dio -0.06375 mm â†’ diferencia 0.4% (por triangular vs uniforme).
- Equilibrio cierra con error 0.000000 en G, Q, EX.

### SecciÃ³n L de viga (losa colaborante ACI)
Calculada geomÃ©tricamente, NO inventada. Ala = luz/4 (criterio ACI).
- Alma: 25 x 35 cm | Ala (losa): 100 x 15 cm
- **A = 0.2375 mÂ²**
- **Iz (gravedad) = 4.62842654e-3 mâ´** â† flexiÃ³n vertical
- **Iy (lateral) = 2.07271107e-2 mâ´**
- **J = 2.03909066e-3 mâ´**

IMPORTANTE: en OpenSees las inercias van "cruzadas" en la llamada
`element` porque con `geomTransf vecxz=(0,0,1)` el eje local *y* queda
vertical. Por eso se pasa `Iy_pass = Iz_vig` (gravedad) e
`Iz_pass = Iy_vig` (lateral). No cambiar sin entender esto.

## Seguridad del servidor

Por defecto escucha **solo en `127.0.0.1`**: nadie fuera de tu equipo
llega. Unity corre en la misma mÃ¡quina, asÃ­ que alcanza.

```bash
python servidor_opensees.py          # solo este equipo
python servidor_opensees.py --lan    # toda la red local (celular/AR)
```

Antes era `0.0.0.0` (todas las interfaces), o sea que en el WiFi de la
universidad cualquiera podÃ­a mandarle peticiones. **No podrÃ­a robar
nada** â€”el servidor no hace `eval`, `exec`, `subprocess` ni abre
archivos, solo arma un modelo con nÃºmerosâ€” pero sÃ­ tumbarlo con un
modelo enorme.

Para la fase de AR (Semana 6) harÃ¡ falta `--lan` para conectar desde el
celular. Ãšsalo solo en una red de confianza.

El `traceback` ya no viaja en la respuesta HTTP: incluÃ­a rutas absolutas
del disco (usuario y estructura de carpetas). El error completo sigue
saliendo por la consola del servidor. Para volver a incluirlo:
`OPENSEES_DEBUG=1`.

TambiÃ©n hay tope de 32 MB por peticiÃ³n.

## Capacidades del servidor

| | estado |
|---|---|
| Barras (viga/columna/diagonal), cualquier secciÃ³n y orientaciÃ³n | âœ… |
| OrientaciÃ³n explÃ­cita de secciÃ³n (`vecxz`) | âœ… |
| Apoyos por grado de libertad (empotrado, rÃ³tula, deslizante) | âœ… |
| Diafragmas rÃ­gidos de piso | âœ… |
| Brazos rÃ­gidos / `rigidLink` (muro como columna ancha) | âœ… |
| Varios casos de carga en una peticiÃ³n | âœ… |
| Fiber Sections / no lineal | âŒ pendiente |
| Elementos de Ã¡rea (shell) | âŒ los muros van como barra equivalente |

### Apoyos

`"fijo": true` equivale a `"restricciones": [1,1,1,1,1,1]`. El orden es
`[ux, uy, uz, rx, ry, rz]`, `1` = restringido.

```json
{"id": 2, "x": 4.0, "y": 0.0, "z": 0.0, "restricciones": [1,1,1,0,0,0]}
```

Verificado: con rÃ³tulas el marco es 4Ã— mÃ¡s flexible bajo EX y las
reacciones de momento caen a 0.

### Diafragmas rÃ­gidos

```json
"diafragmas": [{"nodo_maestro": 99, "nodos": [5,6,7,8], "perpendicular": 3}]
```

`perpendicular: 3` = diafragma horizontal. El nodo maestro debe existir
(normalmente en el centro de masa del piso) y todos los nodos deben
compartir la cota â€” si no, se rechaza.

Los DOF **fuera del plano** del maestro (`uz, rx, ry` para `perp=3`) se
restringen solos, porque el diafragma no los toca y dejarÃ­an la matriz
singular. Queda anotado en `avisos`.

> **Un diafragma NO obliga a que todos los nodos tengan el mismo `ux`.**
> El piso se mueve como cuerpo rÃ­gido *en su plano*, y con carga
> excÃ©ntrica ademÃ¡s **rota**. Lo que debe cumplirse es:
> - todos comparten el mismo giro `rz`
> - `ux_i = ux_m âˆ’ rzÂ·(y_i âˆ’ y_m)` y `uy_i = uy_m + rzÂ·(x_i âˆ’ x_m)`
>
> Verificado con error de 4.3e-19 m. Confundir esto es un error fÃ¡cil:
> parece que el diafragma "no funciona" cuando sÃ­ lo hace.

### Brazos rÃ­gidos (muro como columna ancha)

```json
"brazos_rigidos": [{"maestro": 10, "esclavo": 11, "tipo": "beam"}]
```

`beam` = traslaciones **y** rotaciones solidarias. `bar` = solo
traslaciones. Es el mecanismo para que un muro tenga ancho: la barra
equivalente va en su eje y las vigas que llegan a las **caras** se
conectan con brazos rÃ­gidos. Sin esto el muro se comporta como si
tuviera espesor cero.

### Varios casos de carga en una peticiÃ³n

```json
"casos_de_carga": [
  {"nombre":"G",  "cargas_distribuidas":[...]},
  {"nombre":"EX", "cargas_nodales":[...]}
]
```

Se resuelven todos sobre el **mismo modelo ensamblado**. La respuesta
trae `casos` (una lista). Con un solo caso la respuesta sigue siendo
plana, como antes.

Entre casos hay que hacer tres cosas, y omitir cualquiera da resultados
silenciosamente malos:

| llamada | si falta |
|---|---|
| `ops.reset()` | los desplazamientos del caso anterior se acumulan |
| `ops.setTime(0.0)` | el `timeSeries Linear` escala por el tiempo, y cada `analyze(1)` lo incrementa â†’ **el 2Âº caso saldrÃ­a Ã—2** |
| `ops.remove('loadPattern', tag)` | las cargas anteriores siguen actuando |

Verificado en `test_servidor.py`: resolver N casos sobre un modelo da
**idÃ©ntico** (diferencia 0.00e+00) a reconstruirlo para cada caso.

## Ejes locales de los elementos (servidor)

La `geomTransf` se elige por la **geometrÃ­a** del elemento, nunca por su
etiqueta `tipo`:

| geometrÃ­a | `vecxz` por defecto | inercias |
|---|---|---|
| vertical | `(1,0,0)` | derechas (`Iyâ†’Iy`, `Izâ†’Iz`) |
| horizontal o inclinado | `(0,0,1)` | **cruzadas** (`Izâ†’Iy`, `Iyâ†’Iz`) |

El cruce existe porque con `vecxz=(0,0,1)` el eje local *z* queda en el
plano vertical, asÃ­ que la flexiÃ³n por gravedad es alrededor del eje
local *y* â€” hay que poner ahÃ­ la inercia de gravedad.

Antes se elegÃ­a con `transf = 1 if tipo == 'columna' else 2`, y eso
**reventaba con cualquier vertical que no se llamara exactamente
"columna"** (un muro, por ejemplo): recibÃ­a `vecxz=(0,0,1)`, paralelo a
su propio eje, y OpenSees morÃ­a con *"Error initializing coordinate
transformation"*.

### Orientar una secciÃ³n a mano (`vecxz`)

Un elemento puede traer su propio `vecxz`, y es lo que se necesita para
los muros: hay que decirle hacia dÃ³nde apunta su eje fuerte.

```json
{"id":1,"n1":1,"n2":2,"seccion":"muro","tipo":"muro","vecxz":[1,0,0]}
```

Verificado: un muro en voladizo con `Iy/Iz = 25`, girado 90Â° con `vecxz`,
cambia su flexibilidad lateral exactamente por 25.00.

El servidor rechaza un `vecxz` paralelo al eje, un elemento de largo
cero y un nodo inexistente, con mensaje explÃ­cito.

### `avisos`

Si la etiqueta `tipo` no calza con la geometrÃ­a (un `"columna"`
horizontal, una `"viga_x"` vertical), el modelo **se resuelve igual**
â€”manda la geometrÃ­aâ€” pero la respuesta trae el aviso en `avisos`, y
Unity los muestra como warnings. Sirve para cazar datos mal importados
del DXF.

## Fuerzas internas: eleForce vs localForce

**`ops.eleForce(tag)` devuelve fuerzas en ejes GLOBALES**, no locales.
Para leer N/V/M de una barra hay que usar:

```python
ops.eleResponse(tag, 'localForce')
# -> [N_i, Vy_i, Vz_i, T_i, My_i, Mz_i,  N_j, Vy_j, Vz_j, T_j, My_j, Mz_j]
```

Bajo gravedad: cortante vertical en **Vz** (idx 2), momento flector en
**My** (idx 4 y 10).

Esto engaÃ±Ã³ al proyecto durante la Semana 1. Para una viga que corre en
**X**, el eje local x coincide con el global X, asÃ­ que leer `eleForce`
con etiquetas locales *parecÃ­a* funcionar. Para una viga que corre en
**Y**, el momento de gravedad aparece en la casilla `Mx` global â€” que si
se lee como "torsiÃ³n" hace creer que la viga no flecta y que el modelo
estÃ¡ malo. No lo estaba.

Chequeo que lo detecta (y que el equilibrio no puede hacer): en el marco
cuadrado, las vigas X e Y deben tener esfuerzos **locales idÃ©nticos** por
simetrÃ­a. `benchmark_distribuida.py` lo verifica automÃ¡ticamente.

## Casos de carga (obligatorios)

- **G**: gravedad (peso propio + losa + terminaciones), por Ã¡reas
  tributarias â†’ cargas sobre vigas.
- **Q**: carga viva, misma geometrÃ­a tributaria, distinta intensidad.
- **EX**: sismo pseudoestÃ¡tico lateral en X.
- **EY**: sismo pseudoestÃ¡tico lateral en Y.

SuperposiciÃ³n lineal: `R = sum(lambda_i * R_i)`. Cambiar factores de
combinaciÃ³n NO requiere reanÃ¡lisis; cambiar secciÃ³n/apoyo/E/geometrÃ­a SÃ.

## Cargas: Ã¡reas tributarias

- La losa NO se modela como placa. Su carga se transfiere a las vigas
  por **Ã¡reas tributarias**, trazando bisectrices a 45Â° desde las
  esquinas del paÃ±o. Implementado en
  `modelo_benchmark.area_tributaria_viga(luz_viga, luz_transversal)`.
- Con `a` = luz de la viga y `b` = luz transversal del paÃ±o:

  | caso | forma | Ã¡rea |
  |---|---|---|
  | `b <= a` (viga **larga**) | trapecio | `b*(2a - b)/4` |
  | `b > a` (viga **corta**) | triÃ¡ngulo | `aÂ²/4` |

  PaÃ±o cuadrado: ambas dan `LÂ²/4`, las 4 vigas iguales. Por eso el
  benchmark 4Ã—4 no cambiÃ³ al generalizar.
- Debe conservarse la carga: `carga transferida = q * A_tributaria`.
  Se cumple siempre: `2*A_larga + 2*A_corta = Lx*Ly`.

> **El equilibrio NO valida el reparto.** Si le das el doble a una viga
> y la mitad a otra, la suma de reacciones sigue cerrando con error
> 1e-14. Por eso existe `test_areas_tributarias.py`, que verifica
> conservaciÃ³n, geometrÃ­a y simetrÃ­a para 8 relaciones de aspecto.
> En un paÃ±o 6Ã—4 el reparto viejo (`q*Lx*Ly/4` para todas) cargaba la
> viga larga un **33% de menos** y la corta un 33% de mÃ¡s.
- En OpenSees se aplica con `ops.eleLoad('-ele', tag, '-type',
  '-beamUniform', wy, wz, wx)`. La gravedad va en **wz** (2Âº valor).

## Lo que FALTA (prÃ³ximas semanas)

- [ ] Edificio completo desde los DXF reales (tenemos los planos:
      archivos `2017_67-*.dxf`, ejes ya extraÃ­dos).
- [ ] Muros como elementos lineales equivalentes.
- [ ] Diafragmas rÃ­gidos.
- [ ] **Fiber Sections** (no lineal): curva M-Ï†, curvas P-M para
      columna y muro. Esto es OpenSees no lineal, aÃºn no empezado.
- [ ] Unity: visor con toggles (nodos, vigas, columnas, muros,
      diafragmas, apoyos, ejes locales, IDs, Ã¡reas tributarias,
      cargas, deformada, diagramas, demanda-capacidad).
- [ ] AR sobre el edificio real (Semana 6).
- [ ] Sidequests: Tributary Area Inspector, Load Combination Explorer,
      Section Capacity Explorer, "quÃ© carga genero donde estoy".

## Leer los planos DXF (dos trampas que ya costaron caro)

Los DWG se convierten con `accoreconsole.exe` de AutoCAD a una ruta
**sin espacios ni tildes** (`C:\dxf_planos\`) y se leen con `ezdxf`.
**Unidades del DXF: centímetros.** Casi todo el dibujo vive dentro de
bloques: hay que explotar los `INSERT` con `virtual_entities()`.

Capas: `RLE-EJE` trae los globos (`CIRCLE`) y etiquetas (`MTEXT`) de los
ejes; `RLE-EJES` trae las líneas; `RLE-MURO` los muros.

**1. El globo de un eje no está sobre su eje.** Cuando dos ejes quedan
más cerca que un diámetro de globo, el dibujante corre el globo y lo une
a su eje con un **quiebre**: tramo corto horizontal, luego vertical
hasta la línea larga. Leer la altura del globo da la coordenada
equivocada — así aparecieron los "ejes fantasma" 46.92 y 65.22, que en
realidad son los ejes 3' (47.701) y 1b (64.651).

**2. Una lámina trae varias plantas, cada una en su propio origen.** No
se pueden comparar coordenadas crudas entre láminas. Hay que referenciar
cada planta por su grilla; acá se usa el cruce **eje E × eje 3**. La
comprobación de que la traslación quedó bien es que un mismo muro caiga
en coordenadas idénticas desde láminas distintas.

`verificar_planos.py` hace las dos cosas y falla si el modelo se aparta
más de 1 cm del plano.

## Archivos clave

- `verificar_planos.py` — contrasta el modelo contra los DXF: ejes
  (siguiendo el quiebre de los globos) y muros planta por planta.
- `ModeloEstructural.cs` â€” clases de datos de Unity (fuente de verdad).
- `test_contrato_unity.py` â€” verifica que los campos del C# calcen con
  el JSON y con la respuesta del servidor.
- `test_servidor.py` â€” tests del servidor (multi-caso, diafragmas,
  brazos rÃ­gidos, apoyos, entradas invÃ¡lidas).
- `test_areas_tributarias.py` â€” tests del reparto de losa.
- `modelo_benchmark.py` â€” **fuente de verdad del modelo**: geometria,
  material, secciones, cargas y funciones de construccion/solucion.
  Los demas scripts importan de aqui. Si cambias el modelo, cambialo
  SOLO aca.
- `generar_json_unity.py` â€” corre OpenSees y exporta `modelo_unity.json`
  (en la raiz del proyecto; copiar a `Assets/StreamingAssets/`).
- `VisorEstructura.cs` â€” script Unity que lee el JSON y dibuja.
- `servidor_opensees.py` â€” servidor Flask (Honors: reanÃ¡lisis en vivo).
- Los `.dxf` â€” planos estructurales reales del edificio.

## Unity: arquitectura de los scripts

Tres archivos con responsabilidades separadas. **No dupliques clases
entre ellos** â€” Unity no compila si una clase se declara dos veces.

| archivo | responsabilidad |
|---|---|
| `ModeloEstructural.cs` | **Todas** las clases de datos. Fuente de verdad. |
| `VisorEstructura.cs` | Solo dibuja. Carga el JSON y renderiza. |
| `AnalizadorEstructural.cs` | Solo habla con el servidor. Delega el dibujo. |

Antes habÃ­a dos juegos de clases incompatibles (`NodoJSON` vs `Nodo`),
asÃ­ que el visor no podÃ­a mandar lo que dibujaba y el analizador no
podÃ­a dibujar lo que mandaba â€” solo movÃ­a esferas, sin barras.

### Los tres lÃ­mites de JsonUtility que mandan sobre el diseÃ±o

1. **No lee diccionarios con claves arbitrarias.** Por eso `secciones`
   es una LISTA y la respuesta del servidor tambiÃ©n. El servidor acepta
   ambas formas, pero el JSON para Unity debe usar lista.
2. **Solo campos pÃºblicos** de clases `[System.Serializable]`. Las
   propiedades `get/set` las ignora.
3. **Serializa siempre todos los campos.** Un array sin asignar sale
   como `[]`. El servidor trata la lista vacÃ­a como "ausente".

> **Falla en silencio.** Si un campo C# no calza con la clave del JSON,
> no hay error ni warning: queda en su valor por defecto. Una `uz` mal
> escrita da deformada plana sin decir nada.
> `test_contrato_unity.py` compara los campos del C# contra las claves
> reales del JSON y de la respuesta del servidor.

### CÃ³mo se conectan en la escena

```
[Visor]        -> VisorEstructura      (carga modelo_unity.json, dibuja)
[Analizador]   -> AnalizadorEstructural (campo 'visor' apunta a [Visor])
```

`AnalizadorEstructural` toma el modelo de `visor.Modelo`, lo manda con
`JsonUtility.ToJson` **sin transformarlo**, y le devuelve los
desplazamientos al visor. `MostrarCaso("EX")` cambia el caso dibujado
sin volver a consultar: los 4 casos ya estÃ¡n en memoria.

## Formato del JSON (contrato Unity â†” OpenSees)

```json
{
  "nodos": [
    {"id":1,"x":0,"y":0,"z":0,"fijo":true,"ux":0,"uy":0,"uz":0}
  ],
  "elementos": [
    {"id":1,"n1":1,"n2":5,"tipo":"columna"}
  ]
}
```
tipo puede ser: "columna", "viga_x", "viga_y", "muro".

### Dimensiones de dibujo: `largo` y `espesor`

**Toda** seccion lleva dos campos extra ademas de las propiedades
mecanicas:

```json
{"nombre":"viga_x","A":0.18,"Iy":0.00135,"Iz":0.0054,"J":0.0037,
 "largo":0.60,"espesor":0.30}
```

- `largo` = el lado de la **inercia fuerte**: el CANTO de la viga, el
  LARGO del muro, el lado de la columna.
- `espesor` = el ancho.

El servidor los **ignora** (solo lee `A, Iy, Iz, J`). Existen para que
Unity dibuje cada barra con su seccion real en vez de un cilindro de
grosor fijo. Se calculan en `export_unity.py`: Unity NO los deduce de
`A` e `Iy`.

La orientacion sigue el mismo criterio con que el servidor arma la
`geomTransf`, para que dibujo y calculo no discrepen: `vecxz` explicito
si lo hay (muros), si no, vertical -> `(1,0,0)` y horizontal -> canto
vertical.

> `test_contrato_unity.py` comparaba `secciones[0]`, que es una
> columna, contra el JSON del BENCHMARK, que no tiene muros: los campos
> que solo trae el muro no los miraba nadie. Ahora revisa el JSON del
> edificio, exige `largo`/`espesor > 0`, y comprueba
> `A = largo * espesor` y que el `largo` sea de verdad el lado de la
> inercia fuerte.

## Convencion de las inercias: `Iz` es la de GRAVEDAD

En el contrato JSON, para una seccion de viga:

```
Iz = GRAVEDAD  (b*h^3/12, la del canto)
Iy = LATERAL   (h*b^3/12)
```

Y el servidor las **cruza** al armar el elemento, pero **solo si el
elemento NO es vertical**:

| geometria | que hace el servidor | donde queda la fuerte |
|---|---|---|
| vertical (columna, muro) | no cruza | casilla `Iy` |
| viga (horizontal) | `Iy_pass = Iz` | casilla `Iy`, viniendo de `Iz` |

> **Esto ya provoco un bug.** `benchmark_3d.py` tenia los nombres al
> reves (`Iy` = gravedad). El modelo local salia bien igual, porque su
> llamada `element` tambien estaba al reves y los dos errores se
> cancelaban. Pero el JSON exportado sale con los nombres del contrato,
> asi que el servidor cruzaba segun la convencion buena y armaba un
> modelo **4% mas flexible**: 0.22 mm de diferencia.
>
> **El round-trip no lo veia porque comparaba solo REACCIONES**, y esas
> son iguales por estatica pase lo que pase con la rigidez. Es el mismo
> "el equilibrio NO valida el reparto" de siempre. Ahora `export_unity`
> compara tambien los **desplazamientos** nodo a nodo contra
> `benchmark_3d.py` y **aborta** si difieren mas de 1e-6 m.

### La deformada se borra al editar (y avisa)

`EditorEstructura.MarcarModificado()` llama a `visor.LimpiarDeformada()`
cada vez que se toca el modelo: mover un nodo, borrar, cambiar seccion.
Es a proposito -- los desplazamientos anteriores ya no corresponden a la
geometria nueva.

El problema es que despues **el toggle "Deformada" quedaba encendido sin
hacer nada**: `PosicionDe` no encontraba desplazamientos para ningun
nodo y devolvia la posicion original, asi que el edificio se veia
intacto y parecia que *no se deformaba*. Falla en silencio, como el
resto de las trampas de este proyecto.

Ahora `Redibujar()` detecta el caso, **apaga el toggle solo** y explica
por consola que hay que apretar ENTER para recalcular. El panel del
editor tambien lo dice, y `visor.HayDeformada` lo expone.

### El JSON de Unity es GENERADO: no se edita a mano

`data/unity/ingenieria.json` y su copia en `StreamingAssets` los
reescribe `export_unity.py` en cada corrida. Una edicion a mano se
pierde en la siguiente, sin aviso.

Para que un cambio del modelo sea permanente va en
`benchmark_3d.py`. El JSON es la salida, no la fuente.

### Un muro tambien puede venir ACHURADO

No todos los muros estan dibujados con las lineas de `RLE-MURO`.
Algunos van como **HATCH rojo** (color 1, capas `RLA-HATCH2` y
`RLE-HATCH`), con el rotulo `M.H.A. e=NN` al lado -- Muro Hormigon
Armado y su espesor. En planta se ven como una franja de 20-30 cm, que
es justo la forma de un muro visto desde arriba.

Leyendo solo las lineas faltaban dos:

| achurado | donde | que era |
|---|---|---|
| `ANSI37` | X 8.27-11.42, Y 60.10-60.30 | el tramo oeste del muro del eje 1'', en el 1o subterraneo |
| `FP_2` | X 7.67-7.87, Y 55.57-57.93 | cerraba el HUECO entre los dos muros del eje E |

> `verificar_planos.py` tambien lee ahora los hatch, tomando su
> contorno como si fueran las caras del muro. Si no, el verificador
> rechazaria muros que el plano si dibuja -- que fue exactamente lo que
> paso al agregarlos.

Un tercer achurado (`FP_3`, 1.57 m de ancho, con el rotulo `PASADAS`)
NO es muro: es una zona de aberturas de losa. El ancho lo delata.

### La grilla va por donde estan los PILARES, no por el eje vecino

En la banda de la junta de dilatacion hay dos ejes a 0.55 m, y cada uno
lleva una cosa distinta:

```
   pilar de 70x70   Y 63.751 -> 64.451     eje 1   (centro 64.101)
   ..... junta de 0.10 m .....
   muro             Y 64.551 -> 64.851     eje 1b
```

El modelo tenia la grilla en **64.65 (eje 1b)**, o sea sobre el muro, y
las columnas quedaban METIDAS DENTRO de el, cruzando la junta. Los 24
pilares de esa banda estan en **Y = 64.101** en las seis plantas.

Corregido a 64.10. Los muros no usan la grilla -- van en coordenadas
propias -- asi que siguen en 64.65 y sus brazos los alcanzan a 0.55 m.
Con eso el modelo reproduce la junta sin que se la pongan a mano: el
borde del pilar queda en 64.45 y la cara del muro empieza en 64.55,
**0.10 m exactos**.

> La leccion es la misma que con los globos: dos ejes vecinos del plano
> NO son intercambiables. Hay que mirar QUE cuelga de cada uno.

### La grilla es de PORTICOS, no de ejes

Un eje del plano no implica un pilar. Contrastando la capa `RLE-PILAR`
de las plantas contra la grilla aparecio que **el plano tiene 18
pilares por piso y el modelo ponia 40**: sobraban 115 de 190, el 61%,
con 2846 kN de peso propio inventado.

| | ejes CON pilar | ejes SIN pilar |
|---|---|---|
| X | E, F, G, H, I, I' | **Ea (11.32), Ed (14.72)** |
| Y | 3 (47.95), 2 (55.20), 1 (64.10) | **2a (50.26), 1'' (60.20)** |

`Ea` y `Ed` son las **caras del nucleo** de escalera/ascensor: ahi lo
que hay son muros, no columnas. `2a` y `1''` son ejes de muro y de
referencia.

> **Los ejes se QUEDAN en la grilla aunque no lleven pilar.** De ellos
> cuelgan dos cosas: las vigas, y los brazos rigidos con que los muros
> se atan al marco. Sacarlos dejaba **13 de 25 muros sin ningun nudo a
> menos de 4 m** -- los cuatro del nucleo entre 4.65 y 5.29 m --, o sea
> el nucleo desconectado. Lo que cambia es `hay_pilar(ix, iy)`, que
> decide donde va COLUMNA; el nudo existe igual.

El efecto es grande y va en la direccion esperada: menos columnas y
vanos que ya no se apoyan a media luz dan un edificio mas flexible.

| | antes | con los pilares reales |
|---|---|---|
| columnas | 190 | **84** (18 por piso, las del plano) |
| G | 55 456 kN | **52 804 kN** |
| UZ max bajo G | 6.95 mm | **16.47 mm** |
| deriva EX / EY | 1/2516 / 1/942 | **1/1858 / 1/493** |

### Vigas SECUNDARIAS: un eje sin pilar que si lleva viga

Los tres vanos de 10 m del eje F-G-H-I estan partidos por la mitad por
vigas secundarias, en X = 23.02, 33.02 y 43.02. No tienen globo ni
pilar, pero el plano las dibuja en las cuatro plantas altas, de
Y 48.251 a 54.901 y de 55.501 a 63.801.

Eso obliga a separar dos ideas que hasta aqui eran la misma:

```python
IX_SIN_PILAR   = {1, 2, 4, 6, 8}   # Ea, Ed y los tres de viga secundaria
IX_SIN_VIGA_Y  = {1, 2}            # solo Ea y Ed
```

Ea y Ed no llevan ninguna de las dos cosas. Los de viga secundaria no
llevan pilar pero SI su viga, que es su razon de ser.

> **El descenso maximo se DUPLICA**, de 11.58 a 22.30 mm, y es real: el
> punto que mas baja es el cruce de una viga secundaria con el eje 2,
> a media planta y sin pilar debajo. Antes ese nudo no existia en el
> modelo, asi que su flecha era invisible -- el mismo efecto que
> documenta "Vigas subdivididas" para el benchmark. 22.3 mm sobre una
> luz de 8.90 m es L/399.

### Una viga secundaria no siempre cruza el edificio entero

Las de 23.02, 33.02 y 43.02 tienen los DOS tramos: Y 48.251-54.901 y
55.501-63.801. Las de 20.22 y 25.52 solo el sur (del eje 3' al 2). Se
reviso en las cinco plantas: el tramo norte no existe en ninguna.

`VIGA_Y_SOLO_ENTRE[ix] = (iy desde, iy hasta)` acota el tramo, y
`existe()` niega ademas los nudos de ese eje fuera del rango -- si no,
quedan nudos que solo parten una viga en X.

Y el reparto tributario tiene que calcular los ejes que parten el pano
**por BANDA**, no por nivel: un eje puede partir la banda 3'-2 y no la
2-1, y ahi el pano va de largo. Calculandolo por nivel se perdian
67.5 kN de losa.

### Un eje puede existir en unos pisos y en otros no

El eje 25.52 es una SEGUNDA subdivision: parte por la mitad el
sub-vano 23.02-28.02 que quedo al dividir F-G. Pero solo esta en dos
pisos, no en los cuatro:

| planta del plano | piso del modelo | ¿esta? |
|---|---|---|
| Cielo 1o subterraneo (−4.01) | piso 1 | no |
| **Cielo piso 1o (−0.05)** | **piso 2** | **si** |
| **Cielo piso 2o (+3.91)** | **piso 3** | **si** |
| Cielo piso 3o y 4o | pisos 4 y 5 | no |

`EJE_SOLO_EN_NIVELES[ix]` da los niveles donde ese eje tiene nudos.

> **Cuidado con la nomenclatura.** "Piso 1o" del plano es el piso 2 del
> modelo: el piso i del modelo va del nivel i-1 al i, y lo corona la
> planta de CIELO de ese piso.

Y eso obliga a que `tributarias()` calcule `ix_viga`/`iy_viga` **por
nivel**. Con una lista fija, el reparto intentaba partir el pano en un
eje que arriba no existe y se perdian 225 kN de losa.

### Un nudo sin pilar tiene que justificarse

Un cruce de la grilla que no lleva columna solo se queda si:

  - es cruce REAL de una viga en X con una en Y, o
  - un brazo rigido lo usa para atar un muro al marco
    (`ANCLAJES_BRAZO`, precalculado antes de `existe`)

Si no, el nudo solo parte una viga en dos y no aporta nada. Eran **69
de 330**; quedan 25, todos anclajes de muro.

> Partir una viga NO cambia el resultado: la de Bernoulli es exacta,
> asi que dos tramos colineales dan la misma rigidez y la misma flecha
> que uno. Se comprobo al hacerlo -- G quedo en 49 041.18 kN, el mismo
> numero al kilo. Lo que se gana es un modelo que se lee.

**Al eliminar nudos, las vigas tienen que SALTAR el hueco.** Y de ahi
sale la trampa: el largo del tramo ya no es
`X_axes[ix+1] - X_axes[ix]`. Hay dos mapas, `XBEAM_FIN` y `YBEAM_FIN`,
que dicen a que indice llega cada viga, y **tres** sitios tienen que
usarlos o el equilibrio se rompe:

| sitio | si usa el indice de la grilla |
|---|---|
| `datos_vigas()` | `q*A/L` con L corto -> carga sobreestimada |
| peso propio de vigas | cuenta menos metros de los que hay |
| reparto tributario | reparte mal entre los tramos de un lado |

El primero costo 11 728 kN de error y el ultimo 484. Los tres apuntan
al mismo mapa.

> `existe()` mete el eje metalico por el MISMO filtro. Antes hacia
> `return lev in NIVELES_EJE_J` y cortocircuitaba todo, asi que el
> voladizo conservaba nudos en los ejes 2a y 1'' que no llevan nada.
> Con el filtro, sus diagonales pasan de 10 a 6 -- que son las que
> corresponden: sus vigas estan en Y = 47.95, 55.20 y 64.10.

### Un eje sin pilar tampoco lleva fila de vigas

Los ejes 2a (50.26) y 1'' (60.20) no llevan pilar Y TAMPOCO vigas: se
revisaron las seis plantas y ninguna dibuja viga en esas bandas. Son
ejes de MURO -- los del nucleo corren justo sobre ellos.

Pero **sus nudos se quedan en la grilla**, porque de ellos cuelgan los
brazos rigidos de esos mismos muros. Sacarlos dejaba 8 muros sin brazo,
dos de ellos del nucleo, a 4.7 m del nudo mas cercano.

Eso obliga a que **el pano de losa vaya de eje CON VIGA a eje CON
VIGA**, saltandose los que no la llevan: de 47.70 a 55.20 y de 55.20 a
64.65. Y como el lado en Y del pano viene entonces SUBDIVIDIDO en
varios tramos de viga, su carga se reparte entre ellos en proporcion al
largo. La conservacion sigue exacta: suma de areas tributarias = area
del piso, error 0.00e+00.

> `existe()` ademas niega los nudos de BASE sin pilar. En el nivel 0 no
> hay vigas -- empiezan en el 1 -- asi que un nudo de base sin columna
> no lo usa nadie: quedaban 18 sueltos en el modelo y en el dibujo.

### Todo cruce que arranca sobre la base necesita apoyo ahi

No solo los del oriente. Al quitar dos columnas del eje G que no
llegan al terreno mas bajo, esa linea quedo colgando de las vigas y dio
**152 mm** de descenso bajo peso propio. La regla es general: si un
cruce existe en el nivel 1 pero no en la base, y lleva pilar, hay que
restringirle `uz, rx, ry` en el nivel 1.

### El brazo rigido se mide desde el EJE del muro

`DIST_MAX_BRAZO` compara la distancia **del eje del muro al nudo**,
porque el brazo sale de ahi. Medirla desde el EXTREMO del muro dejaba
pasar brazos mucho mas largos que el tope: llegaron a **9.50 m**, o sea
una viga infinitamente rigida cruzando el edificio.

Y los dos nudos se buscan por cercania **al eje**, no a los extremos.
Buscar por el extremo y medir desde el eje era incoherente: dejaba sin
brazo a muros que tenian un nudo a 50 cm.

### El edificio NO es un prisma

Tres cosas que la grilla rectangular no capturaba, todas leidas de los
planos:

| | que pasa | donde se ve |
|---|---|---|
| **La planta se achica** | del piso 1o hacia arriba no hay nada mas alla del eje 1b; el eje 8 existe solo en el subterraneo | vigas por eje Y en cada planta |
| **Fundacion escalonada** | los ejes H, I e I' se fundan en −4.01, no en −7.97 | elevacion `-300`: el tramo mas bajo tiene 3 pilares, no 6 |
| **Dos voladizos** | uno de hormigon al sur del eje 3, otro metalico al oriente del eje I' | plantas `-102`/`-103` y elevacion `-300` |

Se manejan con `existe(ix, iy, lev)`, que decide si un nudo de la
grilla existe en ese nivel, y con `pano_existe(ix, iy, lev)` para los
panos de losa. **`pano_existe` mira las CUATRO esquinas**: con dos, un
voladizo que muere en mitad de la grilla se da por bueno y luego
revienta al buscar una viga que no se creo.

> Los ids de nodo **no se renumeran**: se dejan HUECOS. OpenSees acepta
> ids no consecutivos, y asi la formula
> `lev*nNodesPerFloor + ix*nY + iy + 1` sigue valiendo en todo el
> archivo. Renumerar habria obligado a tocar cada indice del proyecto.

### El voladizo metalico: acero en un modelo de hormigon

El voladizo del oriente (entre los ejes I' y J, pisos 3o y 4o) es de
ACERO, no de hormigon. La elevacion `-300` lo rotula entero:
`P.M. 300x300x20` (pilares) y `V.M. 300x300x5` (vigas).

**El arriostramiento es una V INVERTIDA (chevron), no una cruz de San
Andres.** La elevacion trae ocho lineas inclinadas, pero son solo DOS
diagonales: cada una va dibujada con sus dos caras y cada cara aparece
duplicada. Y las dos **suben hacia el mismo punto**:

```
izquierda  (49.76, 29.9) -> (51.80, 32.55)   sube a la derecha
derecha    (54.16, 29.9) -> (52.12, 32.55)   sube a la izquierda
```

Convergen arriba en el centro del vano, sobre un **pilar intermedio**
(eje `Jm`, X = 55.57) que no tiene globo propio pero que las plantas
`-102` y `-103` delatan con una viga en Y sobre esa coordenada. En una
cruz de San Andres las diagonales se cruzarian y llegarian a esquinas
opuestas; aca llegan las dos al mismo nudo alto, una por cada lado del
pilar del medio.

Dos cosas que eso obligo a cambiar:

1. **Torsion de Bredt, no Saint-Venant.** Un tubo CERRADO es mucho mas
   rigido a torsion que la suma de sus paredes:
   `J = 4·Am²·t/p`. Usar la formula del rectangulo lleno lo
   subestimaria groseramente. Esta en `props_tubo()`.

2. **`E` y `G` POR SECCION en el contrato del servidor.** Antes solo
   habia un modulo global. Sin esto el servidor calculaba los tubos con
   el `Ec` del hormigon y salia un modelo 8 veces mas flexible: el
   round-trip lo caza con 353 mm de diferencia. Son campos
   **opcionales**; una seccion sin `E` sigue usando el material del
   modelo.

> Un tubo hueco **no cumple** `A = largo · espesor`: el 300x300x5 tiene
> 0.0059 m², no 0.09. `test_contrato_unity.py` excluye a mano las
> secciones no macizas (`pilar_metal`, `viga_metal`, `brazo_rigido`),
> con el motivo escrito, en vez de aflojar el criterio para todas. Y a
> cambio les **exige** que traigan su `E` y `G` propios.

### D.M.: el voladizo de hormigon tambien tiene tirantes

El voladizo sur no queda en voladizo puro: la elevacion
`2017_67-306` (eje F-F') muestra **dos `D.M.`, una por cada lado**,
junto a los mismos `P.M.` y `V.M.` del voladizo metalico.

`D.M. Ø` = **Diagonal Metalica** de seccion REDONDA, no tubo. Miden
4.56 m en el plano y **suben hacia el eje 3**: son TIRANTES que cuelgan
la punta del voladizo del nudo del nivel de arriba, no puntales que la
apoyen desde abajo.

> El **diametro no viene** en el rotulo legible. Se supone Ø 32 mm
> (`DIAM_DM`), que es un tirante razonable para 4 m de voladizo.
> SUPUESTO, no dato.

**Las diagonales van en el plano Y-Z, no en X, y NO forman cruz**: una
por cada lado del balcon, las dos con la misma inclinacion. Cuelgan
SIEMPRE del nivel de arriba. Si a un balcon le falta el nivel superior
simplemente no lleva diagonal, y se apoya en los pilares de acero que
suben desde el balcon de abajo. Colgarlo hacia abajo parece inofensivo
pero deja la diagonal en el mismo vano y con la inclinacion opuesta a
la del piso inferior: las dos juntas forman una X que el plano no
muestra.

### Que es de acero y que es de hormigon

La regla vale para **los dos balcones**, el del sur y el metalico del
oriente:

| | material |
|---|---|
| Pilares del borde del balcon | **acero** (`P.M. 300x300x20`) |
| Diagonales (V invertida y `D.M.`) | **acero** |
| **Vigas del balcon** | **hormigon**, como el resto del edificio |
| Losas, muros, columnas del edificio | hormigon |

O sea que en un balcon **solo son de acero los pilares del extremo y
las diagonales**. Las vigas, aunque estén sobre el eje J, son de
hormigon.

El criterio de la columna no se resuelve mirando solo el eje X, porque
el balcon del sur esta en un eje Y:

```python
def columna_metalica(ix, iy):
    return es_metalico(ix) or iy == IDX_VOLADIZO_SUR
```

> Al pasar las vigas a hormigon, `A_vm/I_vm/J_vm` (el tubo
> `300x300x5`) dejaron de usarse en vigas pero **siguen siendo la
> seccion de las diagonales de la V invertida**. No se borraron.

Van en **dos listas separadas** de las diagonales del voladizo
metalico, porque no son la misma seccion: la V invertida es tubo
`300x300x5` y estas son barra redonda. Mezclarlas hacia que el JSON
exportara todas con una sola seccion y el round-trip acusaba 7.39 mm.

### Brazos rigidos viga-muro

El muro va como **columna ancha**: una barra en su eje. Pero el
diafragma lo sujeta solo **en su plano** (`ux, uy, rz`) y nada lo ata
en vertical, asi que bajo gravedad el muro se quedaba arriba mientras
el resto del piso bajaba:

| | uz bajo G | con la deformada x300 |
|---|---|---|
| techo, nudos de marco | -2.42 mm | 725 mm en pantalla |
| remate del nucleo | -0.20 mm | 59 mm |

En Unity eso se ve como **los muros despegados del edificio**.

La union va del EJE del muro al nudo de marco mas cercano a cada
extremo, que es la distancia que en el edificio real cubre el propio
muro hasta la cara donde apoya la viga. Es tambien lo que le da ancho:
sin ella el muro se comporta como si tuviera espesor cero.

> **No se usa `rigidLink`.** Los nodos de piso ya son esclavos del
> diafragma, y hacerlos ademas esclavos de un vinculo rigido deja dos
> restricciones peleando por los mismos GDL. Se modela como BARRA con
> las secciones x`FACTOR_BRAZO` (=100), que alcanza de sobra para
> comportarse como rigido sin arruinar el condicionamiento numerico.

Resultado: el desfase entre el muro y el nudo al que se une baja de
2.22 mm a **0.09 mm** (de 666 a 28 mm en pantalla). Lo que queda es
rigidez real del nucleo, no un defecto del modelo.

En Unity tienen su propio toggle (`verBrazos`, apagado por defecto) y
color violeta: no son elementos reales y no deberian confundirse con
la estructura.

### Vigas subdivididas y nodos auxiliares

Cada viga se modela como `SUBDIVISIONES_VIGA` (por defecto 4) elementos
en serie. **No es por precisiÃ³n** â€”la viga de Bernoulli es exacta con un
solo elementoâ€” sino porque Unity dibuja cada barra como una recta entre
sus dos nodos: sin nodos intermedios, la flecha del vano es invisible.

| | UZ bajo G |
|---|---|
| nodo de esquina (lo que se dibujaba) | âˆ’0.06348 mm |
| centro del vano (lo que faltaba) | âˆ’0.32963 mm |

Se estaba ocultando el **81%** del descenso real.

Los nodos intermedios llevan `"auxiliar": true` en el JSON y Unity los
pinta mÃ¡s chicos y en gris, con toggle propio. El servidor ignora ese
campo. Los ids originales (1â€“8) **no cambian**, para que el nodo 5 siga
siendo el de referencia del nÃºmero de oro.

> Al subdividir, cuidado con cualquier cÃ³digo que diga "todos los nodos
> por encima de la base": ahora eso incluye los auxiliares. El sismo
> pasÃ³ de 200 kN a 800 kN en silencio hasta que
> `test_contrato_unity.py` lo detectÃ³ por equilibrio.

### Respuesta de `/analizar` (servidor Flask â†’ Unity)

Contrato SEPARADO del anterior. Todo en **listas**, nunca diccionarios
indexados por id: `JsonUtility` de Unity no sabe leer claves numÃ©ricas,
y asÃ­ evitamos la dependencia de Newtonsoft.Json.

```json
{
  "ok": true,
  "error": "",
  "max_desplazamiento": 6.348e-05,
  "desplazamientos": [
    {"id":5,"ux":7.5e-07,"uy":7.5e-07,"uz":-6.348e-05,
     "rx":-0.00019759,"ry":0.00019759,"rz":0.0}
  ],
  "reacciones": [
    {"id":1,"fx":0.0,"fy":0.0,"fz":44.75,"mx":0.0,"my":0.0,"mz":0.0}
  ],
  "fuerzas_elementos": [
    {"id":1,"f":[Pi,V2i,V3i,Ti,M2i,M3i,Pj,V2j,V3j,Tj,M2j,M3j]}
  ]
}
```

`reacciones` trae solo los nodos con `"fijo": true`.
Si algo falla, el servidor responde **HTTP 400** con `ok:false` y el
motivo en `error` â€” el cliente Unity lee el cuerpo igual (un 400 llega
como `ProtocolError`, no como `Success`).

## Reglas para el agente de IA

1. **Verifica siempre el equilibrio** tras cualquier cambio de cargas:
   suma de reacciones = carga aplicada, error < 1e-6.
2. **No rompas la separaciÃ³n** OpenSees/Unity (ver arquitectura).
3. **No modifiques el esquema JSON** sin avisar â€” Unity depende de Ã©l.
4. **Respeta el swap de ejes** Zâ†”Y en toda conversiÃ³n a Unity.
5. Al tocar secciones, recuerda el cruce de inercias en vigas.
6. Todo cambio importante necesita una **verificaciÃ³n numÃ©rica**
   (comparar contra un valor conocido, como el -0.0635 mm del benchmark).
7. Trabaja en ciclo: Issue â†’ Plan â†’ Build â†’ Test â†’ Review.

## TorsiÃ³n (J)

`J` se calcula con la fÃ³rmula de Saint-Venant para secciÃ³n rectangular
llena, en `modelo_benchmark.J_rectangular(b, h)`:

```
J = a*t^3 * [ 1/3 - 0.21*(t/a)*(1 - t^4/(12*a^4)) ]     a=lado largo, t=lado corto
```

Para la columna 30x30 da **J = 1.141e-3 mâ´**.

Antes se usaba `min(Iy,Iz)*0.3` = 2.025e-4 mâ´, que no corresponde a
ninguna fÃ³rmula y subestimaba la rigidez torsional **5.6 veces**. En el
benchmark no se nota (marco simÃ©trico, torsiÃ³n â‰ˆ 0, el nÃºmero de oro no
cambiÃ³), pero en el edificio real con planta irregular y sismo EX/EY sÃ­
importa.

## CÃ³mo verificar que algo quedÃ³ bien

El nÃºmero de oro del benchmark: **UZ techo bajo G = -0.0635 mm**.
Si tras un cambio este valor se rompe sin razÃ³n, algo estÃ¡ mal.

Tanto `benchmark_distribuida.py` como `generar_json_unity.py` ahora
**verifican esto solos** al final y avisan si se rompe. Corre cualquiera
de los dos despuÃ©s de tocar el modelo.

## Contexto de la nota

- No se evalÃºa realismo grÃ¡fico. Se evalÃºa: correcciÃ³n estructural,
  verificaciÃ³n, trazabilidad, comprensiÃ³n, calidad de software,
  utilidad de la visualizaciÃ³n, calidad de la experiencia AR.
- Cualquier integrante puede ser preguntado sobre CUALQUIER parte
  (GDL, ejes locales, diafragmas, Ã¡reas tributarias, superposiciÃ³n,
  Fiber Sections, P-M, correspondencia OpenSeesâ†”Unity, AR).
  â†’ El cÃ³digo debe entenderse, no solo funcionar.
