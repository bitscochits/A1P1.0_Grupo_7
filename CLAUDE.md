# CLAUDE.md — Contexto del proyecto

> Este archivo le da contexto a Claude Code (y a cualquier agente de IA)
> sobre el proyecto. Léelo antes de trabajar en cualquier tarea.

---

## Qué es este proyecto

Laboratorio estructural digital del **Edificio de Ingeniería** de la
Universidad de los Andes, para un curso de "herramientas computacionales
en obras civiles". Es un proyecto grupal (3 estudiantes), de 7 semanas.

**El objetivo NO es un videojuego.** Es construir y verificar un modelo
estructural real y una interfaz para interrogarlo, modificarlo y
entenderlo.

## Arquitectura (regla de oro)

Hay una separación estricta que NO se debe romper:

```
OpenSees (Python)  →  archivos JSON  →  Unity (visualiza)  →  AR
   CALCULA              fuente de          MUESTRA
                        verdad
```

- **OpenSees calcula.** Todo el análisis estructural (desplazamientos,
  reacciones, fuerzas, curvas) sale de Python + OpenSeesPy.
- **Los JSON son la fuente de verdad.** La geometría y resultados viven
  en JSON, independientes de Unity. La escena Unity NO es la fuente de
  verdad del modelo.
- **Unity solo visualiza y edita.** No calcula estructura. Lee JSON y
  dibuja. Puede ayudar a crear/editar datos, pero el cálculo vuelve a
  OpenSees.

**Nunca metas lógica de cálculo estructural en C#/Unity.** Si algo hay
que calcularlo, va en Python/OpenSees y se pasa por JSON.

## Convención crítica de ejes

- **OpenSees:** Z es vertical (convención ingeniería).
- **Unity:** Y es vertical (convención videojuego).
- **Conversión:** `Unity(x, z_opensees, y_opensees)`.
  La altura (z de OpenSees) va a la Y de Unity.

Si el edificio se ve "acostado" en Unity, este swap está mal.

## Unidades

- Todo en **m, kN, kPa** (consistente).
- Para SAP2000 se usa **N, m** → multiplicar fuerzas por 1000.
- Módulo elástico: `Ec = 4700*sqrt(fpc)*1000` (fpc en MPa → kPa).

## Estado actual del proyecto (Semana 1 COMPLETA)

### Benchmark validado ✅
Un marco 3D de prueba: **4 columnas + 4 vigas L**, un piso, 4x4x3 m.
- Columnas: cuadradas 30x30 cm.
- Vigas: sección **L** que representa losa colaborante (NO se modelan
  losas con elementos finitos; se idealizan como vigas L).
- Material: hormigón **G-25** (fpc = 25 MPa, Ec = 23.500 MPa).

**Resultado validado contra SAP2000:**
- Deflexión vertical nodo techo bajo carga G: **UZ = -0.0635 mm**.
- SAP dio -0.06375 mm → diferencia 0.4% (por triangular vs uniforme).
- Equilibrio cierra con error 0.000000 en G, Q, EX.

### Sección L de viga (losa colaborante ACI)
Calculada geométricamente, NO inventada. Ala = luz/4 (criterio ACI).
- Alma: 25 x 35 cm | Ala (losa): 100 x 15 cm
- **A = 0.2375 m²**
- **Iz (gravedad) = 4.62842654e-3 m⁴** ← flexión vertical
- **Iy (lateral) = 2.07271107e-2 m⁴**
- **J = 2.03909066e-3 m⁴**

IMPORTANTE: en OpenSees las inercias van "cruzadas" en la llamada
`element` porque con `geomTransf vecxz=(0,0,1)` el eje local *y* queda
vertical. Por eso se pasa `Iy_pass = Iz_vig` (gravedad) e
`Iz_pass = Iy_vig` (lateral). No cambiar sin entender esto.

## Seguridad del servidor

Por defecto escucha **solo en `127.0.0.1`**: nadie fuera de tu equipo
llega. Unity corre en la misma máquina, así que alcanza.

```bash
python servidor_opensees.py          # solo este equipo
python servidor_opensees.py --lan    # toda la red local (celular/AR)
```

Antes era `0.0.0.0` (todas las interfaces), o sea que en el WiFi de la
universidad cualquiera podía mandarle peticiones. **No podría robar
nada** —el servidor no hace `eval`, `exec`, `subprocess` ni abre
archivos, solo arma un modelo con números— pero sí tumbarlo con un
modelo enorme.

Para la fase de AR (Semana 6) hará falta `--lan` para conectar desde el
celular. Úsalo solo en una red de confianza.

El `traceback` ya no viaja en la respuesta HTTP: incluía rutas absolutas
del disco (usuario y estructura de carpetas). El error completo sigue
saliendo por la consola del servidor. Para volver a incluirlo:
`OPENSEES_DEBUG=1`.

También hay tope de 32 MB por petición.

## Capacidades del servidor

| | estado |
|---|---|
| Barras (viga/columna/diagonal), cualquier sección y orientación | ✅ |
| Orientación explícita de sección (`vecxz`) | ✅ |
| Apoyos por grado de libertad (empotrado, rótula, deslizante) | ✅ |
| Diafragmas rígidos de piso | ✅ |
| Brazos rígidos / `rigidLink` (muro como columna ancha) | ✅ |
| Varios casos de carga en una petición | ✅ |
| Fiber Sections / no lineal | ❌ pendiente |
| Elementos de área (shell) | ❌ los muros van como barra equivalente |

### Apoyos

`"fijo": true` equivale a `"restricciones": [1,1,1,1,1,1]`. El orden es
`[ux, uy, uz, rx, ry, rz]`, `1` = restringido.

```json
{"id": 2, "x": 4.0, "y": 0.0, "z": 0.0, "restricciones": [1,1,1,0,0,0]}
```

Verificado: con rótulas el marco es 4× más flexible bajo EX y las
reacciones de momento caen a 0.

### Diafragmas rígidos

```json
"diafragmas": [{"nodo_maestro": 99, "nodos": [5,6,7,8], "perpendicular": 3}]
```

`perpendicular: 3` = diafragma horizontal. El nodo maestro debe existir
(normalmente en el centro de masa del piso) y todos los nodos deben
compartir la cota — si no, se rechaza.

Los DOF **fuera del plano** del maestro (`uz, rx, ry` para `perp=3`) se
restringen solos, porque el diafragma no los toca y dejarían la matriz
singular. Queda anotado en `avisos`.

> **Un diafragma NO obliga a que todos los nodos tengan el mismo `ux`.**
> El piso se mueve como cuerpo rígido *en su plano*, y con carga
> excéntrica además **rota**. Lo que debe cumplirse es:
> - todos comparten el mismo giro `rz`
> - `ux_i = ux_m − rz·(y_i − y_m)` y `uy_i = uy_m + rz·(x_i − x_m)`
>
> Verificado con error de 4.3e-19 m. Confundir esto es un error fácil:
> parece que el diafragma "no funciona" cuando sí lo hace.

### Brazos rígidos (muro como columna ancha)

```json
"brazos_rigidos": [{"maestro": 10, "esclavo": 11, "tipo": "beam"}]
```

`beam` = traslaciones **y** rotaciones solidarias. `bar` = solo
traslaciones. Es el mecanismo para que un muro tenga ancho: la barra
equivalente va en su eje y las vigas que llegan a las **caras** se
conectan con brazos rígidos. Sin esto el muro se comporta como si
tuviera espesor cero.

### Varios casos de carga en una petición

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
| `ops.setTime(0.0)` | el `timeSeries Linear` escala por el tiempo, y cada `analyze(1)` lo incrementa → **el 2º caso saldría ×2** |
| `ops.remove('loadPattern', tag)` | las cargas anteriores siguen actuando |

Verificado en `test_servidor.py`: resolver N casos sobre un modelo da
**idéntico** (diferencia 0.00e+00) a reconstruirlo para cada caso.

## Ejes locales de los elementos (servidor)

La `geomTransf` se elige por la **geometría** del elemento, nunca por su
etiqueta `tipo`:

| geometría | `vecxz` por defecto | inercias |
|---|---|---|
| vertical | `(1,0,0)` | derechas (`Iy→Iy`, `Iz→Iz`) |
| horizontal o inclinado | `(0,0,1)` | **cruzadas** (`Iz→Iy`, `Iy→Iz`) |

El cruce existe porque con `vecxz=(0,0,1)` el eje local *z* queda en el
plano vertical, así que la flexión por gravedad es alrededor del eje
local *y* — hay que poner ahí la inercia de gravedad.

Antes se elegía con `transf = 1 if tipo == 'columna' else 2`, y eso
**reventaba con cualquier vertical que no se llamara exactamente
"columna"** (un muro, por ejemplo): recibía `vecxz=(0,0,1)`, paralelo a
su propio eje, y OpenSees moría con *"Error initializing coordinate
transformation"*.

### Orientar una sección a mano (`vecxz`)

Un elemento puede traer su propio `vecxz`, y es lo que se necesita para
los muros: hay que decirle hacia dónde apunta su eje fuerte.

```json
{"id":1,"n1":1,"n2":2,"seccion":"muro","tipo":"muro","vecxz":[1,0,0]}
```

Verificado: un muro en voladizo con `Iy/Iz = 25`, girado 90° con `vecxz`,
cambia su flexibilidad lateral exactamente por 25.00.

El servidor rechaza un `vecxz` paralelo al eje, un elemento de largo
cero y un nodo inexistente, con mensaje explícito.

### `avisos`

Si la etiqueta `tipo` no calza con la geometría (un `"columna"`
horizontal, una `"viga_x"` vertical), el modelo **se resuelve igual**
—manda la geometría— pero la respuesta trae el aviso en `avisos`, y
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

Esto engañó al proyecto durante la Semana 1. Para una viga que corre en
**X**, el eje local x coincide con el global X, así que leer `eleForce`
con etiquetas locales *parecía* funcionar. Para una viga que corre en
**Y**, el momento de gravedad aparece en la casilla `Mx` global — que si
se lee como "torsión" hace creer que la viga no flecta y que el modelo
está malo. No lo estaba.

Chequeo que lo detecta (y que el equilibrio no puede hacer): en el marco
cuadrado, las vigas X e Y deben tener esfuerzos **locales idénticos** por
simetría. `benchmark_distribuida.py` lo verifica automáticamente.

## Casos de carga (obligatorios)

- **G**: gravedad (peso propio + losa + terminaciones), por áreas
  tributarias → cargas sobre vigas.
- **Q**: carga viva, misma geometría tributaria, distinta intensidad.
- **EX**: sismo pseudoestático lateral en X.
- **EY**: sismo pseudoestático lateral en Y.

Superposición lineal: `R = sum(lambda_i * R_i)`. Cambiar factores de
combinación NO requiere reanálisis; cambiar sección/apoyo/E/geometría SÍ.

## Cargas: áreas tributarias

- La losa NO se modela como placa. Su carga se transfiere a las vigas
  por **áreas tributarias**, trazando bisectrices a 45° desde las
  esquinas del paño. Implementado en
  `modelo_benchmark.area_tributaria_viga(luz_viga, luz_transversal)`.
- Con `a` = luz de la viga y `b` = luz transversal del paño:

  | caso | forma | área |
  |---|---|---|
  | `b <= a` (viga **larga**) | trapecio | `b*(2a - b)/4` |
  | `b > a` (viga **corta**) | triángulo | `a²/4` |

  Paño cuadrado: ambas dan `L²/4`, las 4 vigas iguales. Por eso el
  benchmark 4×4 no cambió al generalizar.
- Debe conservarse la carga: `carga transferida = q * A_tributaria`.
  Se cumple siempre: `2*A_larga + 2*A_corta = Lx*Ly`.

> **El equilibrio NO valida el reparto.** Si le das el doble a una viga
> y la mitad a otra, la suma de reacciones sigue cerrando con error
> 1e-14. Por eso existe `test_areas_tributarias.py`, que verifica
> conservación, geometría y simetría para 8 relaciones de aspecto.
> En un paño 6×4 el reparto viejo (`q*Lx*Ly/4` para todas) cargaba la
> viga larga un **33% de menos** y la corta un 33% de más.
- En OpenSees se aplica con `ops.eleLoad('-ele', tag, '-type',
  '-beamUniform', wy, wz, wx)`. La gravedad va en **wz** (2º valor).

## Lo que FALTA (próximas semanas)

- [ ] Edificio completo desde los DXF reales (tenemos los planos:
      archivos `2017_67-*.dxf`, ejes ya extraídos).
- [ ] Muros como elementos lineales equivalentes.
- [ ] Diafragmas rígidos.
- [ ] **Fiber Sections** (no lineal): curva M-φ, curvas P-M para
      columna y muro. Esto es OpenSees no lineal, aún no empezado.
- [ ] Unity: visor con toggles (nodos, vigas, columnas, muros,
      diafragmas, apoyos, ejes locales, IDs, áreas tributarias,
      cargas, deformada, diagramas, demanda-capacidad).
- [ ] AR sobre el edificio real (Semana 6).
- [ ] Sidequests: Tributary Area Inspector, Load Combination Explorer,
      Section Capacity Explorer, "qué carga genero donde estoy".

## Archivos clave

- `ModeloEstructural.cs` — clases de datos de Unity (fuente de verdad).
- `test_contrato_unity.py` — verifica que los campos del C# calcen con
  el JSON y con la respuesta del servidor.
- `test_servidor.py` — tests del servidor (multi-caso, diafragmas,
  brazos rígidos, apoyos, entradas inválidas).
- `test_areas_tributarias.py` — tests del reparto de losa.
- `modelo_benchmark.py` — **fuente de verdad del modelo**: geometria,
  material, secciones, cargas y funciones de construccion/solucion.
  Los demas scripts importan de aqui. Si cambias el modelo, cambialo
  SOLO aca.
- `generar_json_unity.py` — corre OpenSees y exporta `modelo_unity.json`
  (en la raiz del proyecto; copiar a `Assets/StreamingAssets/`).
- `VisorEstructura.cs` — script Unity que lee el JSON y dibuja.
- `servidor_opensees.py` — servidor Flask (Honors: reanálisis en vivo).
- Los `.dxf` — planos estructurales reales del edificio.

## Unity: arquitectura de los scripts

Tres archivos con responsabilidades separadas. **No dupliques clases
entre ellos** — Unity no compila si una clase se declara dos veces.

| archivo | responsabilidad |
|---|---|
| `ModeloEstructural.cs` | **Todas** las clases de datos. Fuente de verdad. |
| `VisorEstructura.cs` | Solo dibuja. Carga el JSON y renderiza. |
| `AnalizadorEstructural.cs` | Solo habla con el servidor. Delega el dibujo. |

Antes había dos juegos de clases incompatibles (`NodoJSON` vs `Nodo`),
así que el visor no podía mandar lo que dibujaba y el analizador no
podía dibujar lo que mandaba — solo movía esferas, sin barras.

### Los tres límites de JsonUtility que mandan sobre el diseño

1. **No lee diccionarios con claves arbitrarias.** Por eso `secciones`
   es una LISTA y la respuesta del servidor también. El servidor acepta
   ambas formas, pero el JSON para Unity debe usar lista.
2. **Solo campos públicos** de clases `[System.Serializable]`. Las
   propiedades `get/set` las ignora.
3. **Serializa siempre todos los campos.** Un array sin asignar sale
   como `[]`. El servidor trata la lista vacía como "ausente".

> **Falla en silencio.** Si un campo C# no calza con la clave del JSON,
> no hay error ni warning: queda en su valor por defecto. Una `uz` mal
> escrita da deformada plana sin decir nada.
> `test_contrato_unity.py` compara los campos del C# contra las claves
> reales del JSON y de la respuesta del servidor.

### Cómo se conectan en la escena

```
[Visor]        -> VisorEstructura      (carga modelo_unity.json, dibuja)
[Analizador]   -> AnalizadorEstructural (campo 'visor' apunta a [Visor])
```

`AnalizadorEstructural` toma el modelo de `visor.Modelo`, lo manda con
`JsonUtility.ToJson` **sin transformarlo**, y le devuelve los
desplazamientos al visor. `MostrarCaso("EX")` cambia el caso dibujado
sin volver a consultar: los 4 casos ya están en memoria.

## Formato del JSON (contrato Unity ↔ OpenSees)

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

### Vigas subdivididas y nodos auxiliares

Cada viga se modela como `SUBDIVISIONES_VIGA` (por defecto 4) elementos
en serie. **No es por precisión** —la viga de Bernoulli es exacta con un
solo elemento— sino porque Unity dibuja cada barra como una recta entre
sus dos nodos: sin nodos intermedios, la flecha del vano es invisible.

| | UZ bajo G |
|---|---|
| nodo de esquina (lo que se dibujaba) | −0.06348 mm |
| centro del vano (lo que faltaba) | −0.32963 mm |

Se estaba ocultando el **81%** del descenso real.

Los nodos intermedios llevan `"auxiliar": true` en el JSON y Unity los
pinta más chicos y en gris, con toggle propio. El servidor ignora ese
campo. Los ids originales (1–8) **no cambian**, para que el nodo 5 siga
siendo el de referencia del número de oro.

> Al subdividir, cuidado con cualquier código que diga "todos los nodos
> por encima de la base": ahora eso incluye los auxiliares. El sismo
> pasó de 200 kN a 800 kN en silencio hasta que
> `test_contrato_unity.py` lo detectó por equilibrio.

### Respuesta de `/analizar` (servidor Flask → Unity)

Contrato SEPARADO del anterior. Todo en **listas**, nunca diccionarios
indexados por id: `JsonUtility` de Unity no sabe leer claves numéricas,
y así evitamos la dependencia de Newtonsoft.Json.

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
motivo en `error` — el cliente Unity lee el cuerpo igual (un 400 llega
como `ProtocolError`, no como `Success`).

## Reglas para el agente de IA

1. **Verifica siempre el equilibrio** tras cualquier cambio de cargas:
   suma de reacciones = carga aplicada, error < 1e-6.
2. **No rompas la separación** OpenSees/Unity (ver arquitectura).
3. **No modifiques el esquema JSON** sin avisar — Unity depende de él.
4. **Respeta el swap de ejes** Z↔Y en toda conversión a Unity.
5. Al tocar secciones, recuerda el cruce de inercias en vigas.
6. Todo cambio importante necesita una **verificación numérica**
   (comparar contra un valor conocido, como el -0.0635 mm del benchmark).
7. Trabaja en ciclo: Issue → Plan → Build → Test → Review.

## Torsión (J)

`J` se calcula con la fórmula de Saint-Venant para sección rectangular
llena, en `modelo_benchmark.J_rectangular(b, h)`:

```
J = a*t^3 * [ 1/3 - 0.21*(t/a)*(1 - t^4/(12*a^4)) ]     a=lado largo, t=lado corto
```

Para la columna 30x30 da **J = 1.141e-3 m⁴**.

Antes se usaba `min(Iy,Iz)*0.3` = 2.025e-4 m⁴, que no corresponde a
ninguna fórmula y subestimaba la rigidez torsional **5.6 veces**. En el
benchmark no se nota (marco simétrico, torsión ≈ 0, el número de oro no
cambió), pero en el edificio real con planta irregular y sismo EX/EY sí
importa.

## Cómo verificar que algo quedó bien

El número de oro del benchmark: **UZ techo bajo G = -0.0635 mm**.
Si tras un cambio este valor se rompe sin razón, algo está mal.

Tanto `benchmark_distribuida.py` como `generar_json_unity.py` ahora
**verifican esto solos** al final y avisan si se rompe. Corre cualquiera
de los dos después de tocar el modelo.

## Contexto de la nota

- No se evalúa realismo gráfico. Se evalúa: corrección estructural,
  verificación, trazabilidad, comprensión, calidad de software,
  utilidad de la visualización, calidad de la experiencia AR.
- Cualquier integrante puede ser preguntado sobre CUALQUIER parte
  (GDL, ejes locales, diafragmas, áreas tributarias, superposición,
  Fiber Sections, P-M, correspondencia OpenSees↔Unity, AR).
  → El código debe entenderse, no solo funcionar.
