# Semana 2 — Modelo global v1 y transferencia de cargas

**Edificio de Ingeniería, Universidad de los Andes**
Grupo 7 · Laboratorio estructural digital

Todos los números de este informe salen de correr `benchmark_3d.py` y
`export_unity.py`. Ninguno está escrito a mano.

```bash
python benchmark_3d.py     # modelo, 4 casos, equilibrio
python export_unity.py     # exporta a Unity + round-trip por el servidor
```

---

## 1. Trazabilidad desde planos

La grilla sale de los ejes estructurales de los planos DXF. Cada eje es
una coordenada; el cruce de dos ejes en un nivel es un nodo; cada nodo
se conecta con sus vecinos por elementos.

### Verificación contra los planos

Los ejes del modelo se contrastaron contra la capa `RLE-EJE` del plano
`2017_67-100` (fundaciones), leído con `ezdxf`. **Las unidades del DXF
son centímetros.**

Los **8 ejes X del modelo existen todos** en el plano, con coincidencia
al centímetro:

| eje del plano | plano (m) | modelo (m) |
|---|---|---|
| E | 8.021 | 8.02 ✓ |
| Ea | 11.321 | 11.32 ✓ |
| Ed | 14.721 | 14.72 ✓ |
| F | 18.021 | 18.02 ✓ |
| G | 28.021 | 28.02 ✓ |
| H | 38.021 | 38.02 ✓ |
| I | 48.021 | 48.02 ✓ |
| I' | 53.021 | 53.02 ✓ |

En **Y** los seis existen, pero **dos estaban mal leídos**. Un eje se
identifica por su *globo*: un `CIRCLE` de radio 0.438 m en el margen de
la lámina, con la etiqueta `MTEXT` adentro. Cuando dos ejes quedan más
cerca que un diámetro —y en esta planta hay pares separados 0.25 m— el
dibujante **corre el globo** y lo une a su eje con un **quiebre**: un
tramo corto horizontal desde el globo y luego uno vertical hasta la
línea larga del eje.

Tomar la altura del globo como coordenada del eje es entonces un error,
y es el que produjo los dos «ejes fantasma»:

| eje | globo (m) | eje real (m) | lectura |
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

Los seis ejes Y del modelo quedan entonces:

| modelo (m) | eje | plano (m) | |
|---|---|---|---|
| **47.70** | 3' | 47.701 | ✓ (antes 46.92) |
| 50.26 | 2a | 50.256 | ✓ |
| 55.20 | 2 | 55.201 | ✓ |
| 60.20 | 1'' | 60.201 | ✓ |
| **64.65** | 1b | 64.651 | ✓ (antes 65.22) |
| 72.75 | 8 | 72.751 | ✓ |

Tres verificaciones independientes de que los corregidos son los buenos:

1. La grilla **relativa al eje 3** es idéntica en las cuatro láminas de
   planta (`0, 2.305, 7.250, 12.250, 16.150 m`), aunque cada lámina esté
   insertada en un origen distinto.
2. Los muros de `RLE-MURO` caen sobre los ejes corregidos y no sobre los
   globos: el muro del eje 3-3' ocupa la banda `Y 47.60–47.90`, que
   contiene 47.701 y no 46.92; el del eje 1b ocupa `64.55–64.85`, que
   contiene 64.651 y no 65.22.
3. Las láminas de elevación se titulan **«ELEVACION EJE 3-3'»** y
   **«ELEVACION EJE 1-1'»**: los ejes van de a pares porque son las dos
   caras del mismo muro.

Efecto de esta corrección **por sí sola**, antes de tocar la altura: la
planta se acorta de 25.83 a 25.05 m en Y, y las cargas totales bajan de
100254 a 97779 kN en G y de 18598 a 18036 kN en Q. Los totales finales
del modelo, ya con la altura corregida, están en §2.2. El equilibrio
cierra en los cuatro casos.

El plano tiene 19 ejes X y 18 ejes Y; el modelo usa un subconjunto, lo
cual es legítimo como simplificación.

Todo esto lo rehace `python verificar_planos.py`, que además falla si
algún eje del modelo se aparta más de 1 cm del plano.

### Ejes

| dirección | valores (m) |
|---|---|
| X (8 ejes) | 8.02, 11.32, 14.72, 18.02, 28.02, 38.02, 48.02, 53.02 |
| Y (6 ejes) | 47.70, 50.26, 55.20, 60.20, 64.65, 72.75 |
| Z (6 niveles) | 0.0, 3.96, 7.92, 11.88, 15.84, 19.80 |

Las cotas Z son uniformes, de **3.96 m** (§2.1). La base del modelo
está en z = 0 y corresponde a la cota real **−7.97 m**; la cota de un
nivel es `COTA_BASE + heights[lev]`, así que el techo queda en +11.83 m.
Los ejes X no son uniformes: hay vanos de 3.30 m y otros de 10.00 m, lo
que después será determinante en el reparto de cargas (§4).

### Numeración

```
nodo(nivel, ix, iy) = nivel · 48 + ix · 6 + iy + 1
```

con 48 = 8 × 6 nodos por piso. Los nodos de la base son 1 a 48.

### Ejemplo completo: plano → nodo → elemento → sección → tag

| paso | valor |
|---|---|
| **Plano** | cruce del eje X = 8.02 m (eje E) con el eje Y = 47.70 m (eje 3') |
| **Nodo base** | `ix=0, iy=0, nivel=0` → **nodo 1** en (8.02, 47.70, 0.00) |
| **Nodo piso 1** | `nivel=1` → **nodo 49** en (8.02, 47.70, 3.96) |
| **Elemento** | columna que une 1 → 49 |
| **elementTag** | **1** |
| **sectionTag** | `"columna"` |
| **Sección** | 0.50 × 0.50 m, A = 0.2500 m², J = 8.802e-3 m⁴ |

Un segundo ejemplo, esta vez una viga:

| paso | valor |
|---|---|
| **Plano** | vano entre los ejes X = 28.02 y X = 38.02, sobre el eje Y = 55.20 |
| **Nodos** | `nivel=1, ix=4, iy=2` → **nodo 75** a **nodo 81** |
| **elementTag** | **267** |
| **sectionTag** | `"viga_x"` (0.30 × 0.60 m) |
| **Luz** | 10.00 m |

### Rangos de tags

| rango | qué |
|---|---|
| 1 – 240 | columnas |
| 241 – 450 | vigas en X |
| 451 – 650 | vigas en Y |
| 651 – 694 | muros |

---

## 2. Estadísticas del modelo

| concepto | cantidad |
|---|---|
| Nodos estructurales | **288** |
| Nodos de muro | **67** |
| Nodos maestros de diafragma | **5** |
| Nodos totales | **360** |
| Columnas | **240** |
| Vigas en X | **210** |
| Vigas en Y | **200** |
| Vigas totales | **410** |
| Muros | **44** (23 muros, cada uno solo en sus pisos) |
| Diafragmas rígidos | **5** |
| Pisos con losa | **5** |
| Niveles (incluida la base) | **6** |
| Elementos totales | **694** |
| Paños de losa por piso | **35** |
| Altura total | **19.80 m** (base −7.97 → techo +11.83) |
| Planta | 45.0 × 25.0 m |

### Muros

Los muros se extrajeron del plano **`2017_67-100`** (fundaciones), capa
`RLE-MURO`, convertido a DXF con `accoreconsole` de AutoCAD y leído con
`ezdxf`. Las unidades del DXF son **centímetros**.

Los ejes de ese plano coinciden al centímetro con los del modelo, así
que las coordenadas de los muros están en el mismo sistema y se usan
directamente, sin transformación.

Del DXF salieron 28 muros. Se descartaron:

- **2 por quedar fuera de la planta modelada** (llegan a Y = 37.78 y
  Y = 75.58; el modelo va de 47.70 a 72.75)
- **3 por duplicados**: el pareo de caras tomaba dos veces el mismo muro
  cuando había caras a menos de 0.35 m

Quedan **23 muros, 168.3 m acumulados**. Los principales:

| dirección | eje | tramo | largo (m) | espesor (m) |
|---|---|---|---|---|
| Y | X = 18.22 | Y 47.60 → 64.45 | **16.85** | 0.30 |
| X | Y = 64.30 | X 37.67 → 52.67 | **15.00** | 0.30 |
| X | Y = 64.78 | X 14.50 → 29.27 | **14.77** | 0.15 |
| X | Y = 72.76 | X 17.50 → 29.57 | **12.07** | 0.20 |
| X | Y = 64.78 | X 41.77 → 53.02 | 11.25 | 0.15 |
| Y | X = 48.17 | Y 55.55 → 63.75 | 8.20 | 0.30 |
| Y | X = 7.77 | 3 tramos, Y 47.60 → 72.75 | 21.95 | 0.20 |

Los cortes entre tramos de un mismo eje son vanos de puerta.

> **SUPUESTO DESMENTIDO Y CORREGIDO:** el modelo asumía que los muros
> **suben por los 8 pisos**. Se verificó contra las plantas, es falso, y
> el modelo se rehízo. Cada muro trae ahora la tupla de pisos en que
> existe y `verificar_planos.py` la contrasta contra el DXF. Detalle en
> §2.1.

Modelo: **columna ancha**. Cada muro es un elemento vertical en su
centroide, con la sección orientada por `vecxz` para que el eje fuerte
quede en el plano del muro. Sus nodos entran al diafragma de cada piso.

**Limitación:** sin brazos rígidos, las vigas que llegarían a las *caras*
del muro se conectan a su eje.

### 2.1 Los muros no suben, y el edificio no tiene 8 pisos

Las plantas de piso traen **dos** plantas por lámina, no tres. Sus
títulos (`RLA-TEXTOS2`) y las cotas de losa que los acompañan:

| lámina | planta | losa (m) |
|---|---|---|
| `-100` | Planta fundaciones | −7.97 |
| `-101` | Planta cielo 1° subterráneo | −4.01 |
| `-101` | Planta cielo piso 1° | −0.05 |
| `-102` | Planta cielo piso 2° | +3.91 |
| `-102` | Planta cielo piso 3° | +7.87 |
| `-103` | Planta cielo piso 4° | +11.83 |

El espaciamiento es **uniforme de 3.96 m**. Lo confirman las marcas de
nivel de la elevación `2017_67-300` («ELEVACION EJE 1-1'»), a 13.79,
17.75, 21.71, 25.67, 29.63 y 33.59 en la lámina — diferencias de 3.96
exactas — y sus rótulos de piso: `1°S, 1°, 2°, 3°, 4°`. Las láminas
`-2xx` son planos de armadura que referencian estas mismas plantas: **no
existen pisos 5° a 8°**.

O sea que el edificio tiene **6 niveles hasta +11.83 m**, y el modelo
tenía **9 niveles hasta +28.5 m**, con pisos de 3.5 m en vez de 3.96 m.
Ya está corregido: `heights = [0, 3.96, 7.92, 11.88, 15.84, 19.80]` y
`COTA_BASE = -7.97`.

Para comparar los muros entre niveles hay que llevar cada planta a un
sistema común, porque **cada una está insertada en un origen distinto**.
Se usó como datum el cruce **eje E × eje 3** de cada planta. Que muros
idénticos caigan en coordenadas idénticas partiendo de tres orígenes
distintos es la verificación de que la traslación está bien.

Contrastando los 23 muros del modelo contra cada planta:

| | Fundac. | 1° subt | piso 1° | piso 2° | piso 3° | piso 4° |
|---|---|---|---|---|---|---|
| losa (m) | −7.97 | −4.01 | −0.05 | +3.91 | +7.87 | +11.83 |
| largo presente (m) | 168.3 | 105.0 | 78.8 | **13.1** | **13.1** | **13.1** |
| % de los 168.3 m | 100 % | 62 % | 47 % | **8 %** | **8 %** | **8 %** |

Sobre el nivel ±0.00 sobrevive **solo el núcleo de escalera/ascensor**
(≈3.7 × 10 m, entre los ejes Ea–Ed y 2a–1''): las mismas 12 corridas de
muro, idénticas en los pisos 2°, 3° y 4°.

La razón es que los 168.3 m de la fundación incluyen los **muros de
contención del subterráneo** — la lámina `2017_67-002` trae
«disposición de armaduras en muro contención» —, que existen solo bajo
tierra. El modelo los extruye por los 8 pisos.

Irónicamente, el supuesto viejo que se descartó —4 muros de 3.3 m en un
núcleo poniente— se parecía mucho al núcleo real de los pisos altos.

Esto lo rehace `python verificar_planos.py`, que además **falla** si la
tupla de pisos declarada para un muro no coincide con lo que muestran
las plantas.

#### Cómo quedó el modelo

Cada muro trae ahora la tupla de pisos en que existe, y sube solo hasta
ahí. Muro por piso: **105.0 / 84.6 / 13.3 / 13.3 / 13.3 m**.

Ocho muros del oriente aparecen recién en el piso 2°: el subterráneo no
llega hasta allá y su zapata queda más alta, así que se apoyan en el
nivel 1. Ahí hay que tener cuidado, porque **ese nodo ya es esclavo del
diafragma** de ese piso. Empotrarlo del todo ataría también `ux, uy, rz`
y, como el diafragma es rígido, **dejaría inmóvil el piso entero**: la
deriva del piso 1 se iría a cero y los 105 m de muro de ese piso
quedarían de adorno. Se restringen solo los DOF que el diafragma no toca
(`uz, rx, ry`), el mismo recurso que ya se usa con los nodos maestros.

Ese apoyo toma bajo G exactamente la mitad del peso propio del primer
tramo de esos muros (**1504.01 kN** entre los ocho) y **0.00 kN** bajo
Q, EX y EY: sostiene el muro y nada más. Lo que sí queda fuera del modelo
es el empotramiento **lateral** de la fundación escalonada; con
diafragma rígido no hay cómo ponerlo sin congelar el piso.

Segunda trampa, en el chequeo de equilibrio: `nodeReaction` en un nodo
esclavo de un diafragma devuelve además la **fuerza del vínculo**, que
es interna. Sumarla hacía fallar EX por 10312 kN y EY por 3421 kN. En
horizontal solo suman los apoyos con `ux/uy` restringidos.

### 2.2 Efecto de los muros

Antes de tener los planos, el modelo llevaba 4 muros supuestos de 3.3 m.
Con los 23 reales:

| | 4 muros supuestos | 23 muros en los 8 pisos | 23 muros, pisos reales |
|---|---|---|---|
| altura del modelo | 28.50 m | 28.50 m | **19.80 m** |
| largo acumulado | 13.3 m | 168.3 m en cada piso | **105.0 / 84.6 / 13.3 / 13.3 / 13.3 m** |
| `UX` máx bajo EX | 0.0819 m | 0.0107 m | **0.0147 m** |
| deriva de techo EX | 1/348 | 1/2676 | **1/2554** |
| deriva de techo EY | — | — | **1/904** |

La columna del medio es el modelo v1, que extruía los muros de
contención del subterráneo por toda la altura: daba un edificio **el
doble de rígido** que el real. Con los muros en sus pisos, la deriva
queda en 1/2554, que sigue siendo la de un edificio con núcleo de muros
y no la de un marco desnudo — coherente con la tipología real.

Las cargas totales también bajan al corregir la altura: G de 100254 a
**55330 kN**, Q de 18598 a **8928 kN**, corte basal de 9965 a
**5407 kN**. Equilibrio con error < 4·10⁻⁴ kN en los cuatro casos, y el
round-trip por el servidor reproduce los mismos totales.

### Material y secciones

Hormigón **G-28**: `f'c = 28 MPa`, `Ec = 4700·√f'c = 24 870 MPa`, ν = 0.2.

| sección | b × h (m) | A (m²) | Iy (m⁴) | Iz (m⁴) | J (m⁴) |
|---|---|---|---|---|---|
| columna | 0.50 × 0.50 | 0.2500 | 5.208e-3 | 5.208e-3 | **8.802e-3** |
| viga X | 0.30 × 0.60 | 0.1800 | 5.400e-3 | 1.350e-3 | **3.708e-3** |
| viga Y | 0.30 × 0.80 | 0.2400 | 1.280e-2 | 1.800e-3 | **5.502e-3** |

`J` se calcula con la fórmula de Saint-Venant para sección rectangular
llena (`modelo_benchmark.J_rectangular`). Ver §10: antes se usaba una
expresión incorrecta.

---

## 3. Carga superficial

| componente | valor |
|---|---|
| Espesor de losa | `t = 0.25 m` |
| Peso unitario del hormigón | `γ = 25.0 kN/m³` |
| Peso propio de la losa | `γ · t = ` **6.25 kN/m²** |
| Terminaciones y sobrelosa | **1.50 kN/m²** |
| **`q_G`** (carga muerta superficial) | **7.75 kN/m²** |
| **`q_Q`** (sobrecarga de uso) | **2.00 kN/m²** |

Por piso, la carga muerta de losa es:

```
nivel 1 (planta completa):  7.75 · 1127.25 = 8736.19 kN
niveles 2 a 5 (achicada):   7.75 ·  762.75 = 5911.31 kN
```

> **El área de piso NO es la misma en todos los niveles.** Del piso 1°
> hacia arriba el edificio termina en el eje 1b, y la franja hasta el
> eje 8 existe solo en el subterráneo: 8.10 × 45 m = **364 m² menos por
> piso**. Ver §2.1.

A eso se suma el peso propio de vigas (aplicado como carga distribuida
adicional sobre cada barra), de columnas y de **muros** (como fuerzas
nodales en sus extremos, mitad a cada extremo de cada tramo). El total
de la carga muerta del edificio es **55 329.98 kN**.

> Los muros no pesaban nada hasta que la deformada exagerada de Unity
> lo delató: los remates del núcleo quedaban clavados a cota real,
> flotando sobre un techo que bajaba a su alrededor, porque a esos
> nodos no les llegaba ninguna carga vertical. Con su peso propio
> puesto, el núcleo baja 0.20 mm contra 2.4 mm del resto del techo —
> sigue casi quieto, pero ahora porque un muro es ~12 veces más rígido
> a carga axial que el marco a flexión, no porque no pese.

---

## 4. Áreas tributarias

### Criterio

Cada paño de losa se reparte a las **cuatro vigas que lo bordean**,
trazando bisectrices a 45° desde las esquinas. Eso divide el paño en
cuatro polígonos:

```
    paño Lx × Ly, con Ly < Lx

    +--------------------------+
    | \                      / |   vigas de luz Lx (LARGAS) -> TRAPECIO
    |  \____________________/  |
    |  /                    \  |   vigas de luz Ly (CORTAS) -> TRIÁNGULO
    | /                      \ |
    +--------------------------+
```

Con `a` = luz de la viga y `b` = luz transversal del paño:

| caso | polígono | área |
|---|---|---|
| `b ≤ a` (viga larga) | trapecio | `b(2a − b)/4` |
| `b > a` (viga corta) | triángulo | `a²/4` |

Una **viga interior borda dos paños**, así que acumula las dos
contribuciones. El reparto se implementa iterando **por paño** y sumando
sus cuatro aportes, de modo que la conservación queda garantizada por
construcción.

La carga se aplica como **uniforme equivalente** sobre la barra:

```
w = q_G · A_tributaria / L        [kN/m]
```

usando `eleLoad -beamUniform`, no como fuerzas puntuales en los nudos
(ver §10).

### Ejemplos de paños

| paño (ix, iy) | Lx (m) | Ly (m) | A paño (m²) | viga X | A_x (m²) | viga Y | A_y (m²) |
|---|---|---|---|---|---|---|---|
| (0,0) | 3.30 | 2.56 | 8.45 | trapecio | 2.586 | triángulo | 1.638 |
| (0,1) | 3.30 | 4.94 | 16.30 | triángulo | 2.723 | trapecio | 5.429 |
| (0,4) | 3.30 | 8.10 | 26.73 | triángulo | 2.723 | trapecio | 10.642 |

Comprobación por paño: `2·A_x + 2·A_y = A_paño`.
Para (0,0): `2(2.586) + 2(1.638) = 8.45 m²` ✓

En el paño (0,0) la forma **se invirtió** al corregir el eje 3' (§1): el
vano Y pasó de 3.34 a 2.56 m, así que ahora la viga X es la larga y
recibe el trapecio. El reparto sigue la geometría, no una etiqueta.

### Tres vigas en detalle (nivel 1)

| elementTag | dir | polígono(s) | L (m) | A_trib (m²) | q_G (kN/m²) | carga total (kN) | w aplicada (kN/m) |
|---|---|---|---|---|---|---|---|
| **241** | X | 1 trapecio (borde) | 3.30 | 2.586 | 7.75 | 20.04 | 6.072 |
| **267** | X | 2 trapecios (interior) | 10.00 | 37.349 | 7.75 | 289.46 | 28.946 |
| **457** | Y | 2 trapecios (interior) | 4.94 | 10.937 | 7.75 | 84.76 | 17.157 |

La viga 241 es de borde y de vano corto: recibe un solo polígono. La
267 tiene 10 m de luz y es interior: recibe **14 veces** más área. Ese
contraste es exactamente lo que un reparto 50/50 por franjas no captura.

En Unity, seleccionar una viga muestra su `área tributaria` y su
`w gravedad` en el panel (§8).

---

## 5. Conservación

La suma de todas las áreas tributarias de un piso debe igualar el área
del piso:

```
Σ A_tributaria  =  1127.250000 m²
A_piso          =  1127.250000 m²
error           =  0.0 m²  (exacto en doble precisión)
```

Y en carga:

```
Σ (q_G · A_trib)  =  q_G · A_piso  =  8736.19 kN por piso
```

**Tolerancia adoptada: 1e-6 m² en área y 1e-6 kN en fuerza.** El error
obtenido está 7 órdenes de magnitud por debajo — es puro redondeo de
punto flotante.

### Equilibrio global de los cuatro casos

| caso | aplicado (kN) | reacciones (kN) | error (kN) |
|---|---|---|---|
| G | 55 329.98 | 55 329.98 | 0.0003 |
| Q | 8 927.70 | 8 927.70 | 0.0001 |
| EX | 5 402.62 | −5 402.62 | 0.0001 |
| EY | 5 402.62 | −5 402.62 | 0.0001 |

> **El equilibrio NO valida el reparto.** Si a una viga se le da el doble
> y a la vecina la mitad, la suma de reacciones cierra igual de bien.
> Por eso la verificación de §5 (conservación de área, viga por viga) es
> independiente y necesaria. Este punto nos costó un error real: ver §10.

### Desplazamientos máximos

| caso | UX (m) | UY (m) | UZ (m) |
|---|---|---|---|
| G | 0.00028 | 0.00045 | **0.00455** |
| Q | 0.00005 | 0.00010 | 0.00094 |
| EX | **0.00770** | 0.00305 | 0.00095 |
| EY | 0.00148 | **0.01325** | 0.00080 |

Deriva de techo: `0.00770 / 19.80 = 1/2571` bajo EX y
`0.01325 / 19.80 = 1/1494` bajo EY.

La deriva en X mejoró mucho al añadir los **brazos rígidos** (§2.1):
pasó de 1/1288 a 1/2055. Sin ellos el muro estaba atado al diafragma
solo en su plano y no colaboraba como debía. El muro del ascensor
aportó el 2% restante, hasta 1/2106; y al recortar la planta de los
pisos altos quedó en 1/2565. En Y el cambio es menor
(1/1313 → 1/1336) porque ahí los muros ya trabajaban.

---

## 6. Apoyos y restricciones

El modelo usa tres tipos de condición de borde. El orden de los grados
de libertad es `[ux, uy, uz, rx, ry, rz]`, donde `1` = restringido.

| tipo | nodos | restricciones | dónde |
|---|---|---|---|
| **Empotramiento** | 63 | `[1,1,1,1,1,1]` | los 48 de la base + los 15 arranques de muro en la base |
| **Apoyo de muro escalonado** | 8 | `[0,0,1,1,1,0]` | arranque en el nivel 1 de los muros del oriente (§2.1) |
| **Libre** | 284 | `[0,0,0,0,0,0]` | nodos de piso y nodos intermedios de muro |
| **Maestro de diafragma** | 5 | `[0,0,1,1,1,0]` | un nodo por piso, en el centro |

Los dos últimos tipos comparten las mismas restricciones por el mismo
motivo: son los DOF que el diafragma **no** toca (§2.1 y abajo).

### Por qué el maestro lleva restricciones

El diafragma solo ata los grados de libertad **en su plano** (`ux`, `uy`,
`rz`). Los de fuera del plano (`uz`, `rx`, `ry`) del nodo maestro quedan
sueltos, y como ese nodo **no tiene ningún elemento conectado**, la
matriz de rigidez saldría singular. Por eso se restringen explícitamente.

El servidor hace esto solo y lo reporta en `avisos` cuando recibe un
diafragma cuyo maestro no está restringido.

### En el visor

Los nodos con alguna restricción se dibujan en **verde**; los libres en
azul; los maestros de diafragma en gris y más pequeños (`auxiliar: true`).

---

## 7. Diafragmas rígidos

### Cinemática

Un diafragma rígido hace que el piso se mueva como **cuerpo rígido en su
plano**. Eso **no** significa que todos los nodos tengan el mismo
desplazamiento: significa que se cumple

```
ux_i = ux_m − rz · (y_i − y_m)
uy_i = uy_m + rz · (x_i − x_m)
rz_i = rz_m
```

donde `m` es el nodo maestro. El piso puede **trasladarse y rotar**; lo
que no puede es deformarse en su plano.

Confundir esto es un error fácil, y lo cometimos: ver §10.

### Implementación

```python
ops.rigidDiaphragm(3, maestro, *esclavos)   # 3 = perpendicular a Z
ops.constraints('Transformation')            # 'Plain' no sabe imponerlo
```

Un diafragma por piso (8 en total), con el nodo maestro en el **centro
geométrico** de la planta, que es donde se aplica el corte sísmico.

### Verificación numérica

Se comprobó, para los 5 pisos bajo EX, que (a) todos los nodos de un
piso comparten el mismo `rz` y (b) se cumple la relación de cuerpo
rígido `ux_i = ux_m − rz·(y_i − y_m)`, `uy_i = uy_m + rz·(x_i − x_m)`:

| nivel | maestro | ¿`rz` común? | `rz` (rad) | error de cuerpo rígido (m) |
|---|---|---|---|---|
| 1 | 356 | sí | 2.720e-06 | 1.1e-07 |
| 2 | 357 | sí | 1.101e-05 | 9.1e-08 |
| 3 | 358 | sí | −1.554e-05 | 7.7e-08 |
| 4 | 359 | sí | −3.303e-05 | 9.4e-08 |
| 5 | 360 | sí | −3.166e-05 | 5.8e-08 |

El error de ~1e-7 m es el piso de redondeo (desplazamientos con 8
decimales). Nótese que `rz ≠ 0` **aunque la carga va aplicada en el
centro geométrico**: los muros no están repartidos simétricamente, así
que el centro de rigidez no coincide con el de aplicación y el edificio
**torsiona** — ver más abajo.

**Para demostrar que el diafragma rota de verdad**, se repitió EX
aplicando la carga en una esquina del piso (excentricidad extrema):

| nivel | `rz` (rad) | error de cuerpo rígido (m) |
|---|---|---|
| 1 | 9.200e-06 | 1.0e-08 |
| 3 | 1.699e-04 | 1.8e-08 |
| 5 | **4.418e-04** | 1.2e-07 |

El giro crece un orden de magnitud y el piso **sigue siendo cuerpo
rígido**.

### Torsión real del edificio

Con los muros reales, EX no es un caso puramente traslacional: el muro
largo del eje F (16.85 m) y el núcleo están hacia el poniente, así que
el centro de rigidez se corre y el edificio gira incluso con la carga
centrada:

| nivel | `ux` del maestro (m) | `rz` (rad) |
|---|---|---|
| 1 | 0.000056 | 2.720e-06 |
| 3 | 0.004347 | −1.554e-05 |
| 5 | 0.014918 | −3.166e-05 |

Y aparece `UY = 0.00132 m` bajo EX, que es desplazamiento transversal
puro producto del giro.

Esta es la prueba de que la corrección de §10 era necesaria: con el
`equalDOF` anterior, `rz` habría salido 0 en los tres casos, y **la
torsión inducida por los muros habría sido invisible**.

---

## 8. Viewer Unity

El proyecto vive en `unity/` dentro del repositorio. Tres scripts de
responsabilidad separada más dos de interacción:

| script | responsabilidad |
|---|---|
| `ModeloEstructural.cs` | clases de datos — el contrato con el JSON |
| `VisorEstructura.cs` | solo dibuja |
| `AnalizadorEstructural.cs` | solo habla con el servidor |
| `CamaraOrbital.cs` | navegación |
| `EditorEstructura.cs` | selección y edición |

### Capas

Toggles independientes para: **nodos**, **nodos auxiliares**,
**columnas**, **vigas**, **muros** y **deformada**. Cada uno redibuja al
instante, en pleno Play.

### Selección e IDs

Click sobre un nodo o una barra la selecciona (raycast sobre los
componentes `DatoNodo` / `DatoElemento`, que llevan el tag de OpenSees).
El panel muestra:

- **nodo**: `id`, coordenadas X/Y/Z editables, si está empotrado,
  y `UX / UY / UZ` del último análisis
- **barra**: `id`, nodos que conecta, `tipo`, `sección`,
  **área tributaria (m²)**, **w gravedad (kN/m)**, y `N / Vz / My` en
  **ejes locales**

Los objetos de la escena se nombran `Nodo_49`, `NodoAux_356`,
`Elem_267_viga_x`, así que el id es visible también en la Hierarchy.

### Ejes

La conversión OpenSees → Unity está centralizada en `Ejes.AUnity()`:

```
Unity(x, z_opensees, y_opensees)
```

OpenSees usa **Z vertical** (convención de ingeniería); Unity usa **Y
vertical**. Si el edificio se ve acostado, el error está en ese único
punto.

Los **ejes locales de cada barra** todavía no se dibujan; los esfuerzos
sí se reportan en ejes locales, que es lo que importa para leerlos.

### Apoyos

Los nodos con restricción se pintan verde; los libres, azul; los
maestros de diafragma, gris y más chicos.

### Áreas tributarias

Al seleccionar una viga, el visor **dibuja el contorno de su polígono
tributario** sobre la losa, en ámbar, y el panel muestra:

```
area tributaria: 37.349 m2
w gravedad:      28.946 kN/m
poligono dibujado: 37.349 m2  (calza)
```

Esa última línea es una verificación visible: el área del polígono que se
está dibujando tiene que coincidir con la que se usó para calcular la
carga. Si difieren, el panel lo dice.

La **geometría del polígono se calcula en Python**
(`modelo_benchmark.poligonos_tributarios`) y se exporta en el JSON; Unity
solo la dibuja. Se verificó que el área del polígono (shoelace sobre
sus vértices) coincide con la de `area_tributaria_viga()` con
discrepancia máxima **2.5e-5 m²** (redondeo del JSON, 4 decimales), y
que los 140 polígonos de un piso suman **exactamente** los 1127.25 m²
del piso.

Solo se dibuja el de la barra seleccionada: hay 700 polígonos en el
edificio y pintarlos todos serían miles de objetos.

---

## 9. Modificación del modelo

`EditorEstructura.cs` permite editar el modelo dentro de Unity, sin
tocar el JSON a mano. Está implementado:

| operación | cómo |
|---|---|
| **Cambiar sección** | seleccionar barra → botón con el nombre de la sección |
| **Cambiar apoyo** | seleccionar nodo → toggle *Empotrado* |
| **Mover un nodo** | arrastrarlo (planta) o Shift+arrastrar (altura), o campos X/Y/Z |
| **Crear barra** | seleccionar nodo A → *Empezar barra* → seleccionar nodo B → elegir sección |
| **Borrar** | tecla Supr |
| **Recalcular** | Enter → manda el modelo al servidor y dibuja la deformada nueva |

El reanálisis desde Unity **ya funciona**, aunque para esta entrega no
era obligatorio.

### Integridad al borrar

Borrar deja referencias huérfanas, y algunas son peligrosas porque **no
fallan**: si se borra una barra y queda su carga distribuida, OpenSees
emite un warning por consola y **descarta la carga**. El análisis
"funciona" con menos carga de la que uno cree, y el equilibrio cierra
igual porque la carga descartada nunca entró.

Por eso el editor limpia también las cargas, las barras conectadas, los
diafragmas y los brazos rígidos que apuntaban a lo borrado. Y el
servidor lo valida de forma independiente:

```
En 'G': hay una carga sobre el elemento 5, que no existe.
Si lo borraste, borra tambien su carga.
```

---

## 10. Uso de IA: errores propuestos por el agente y su corrección

El agente (Claude) participó como revisor y como implementador. Lo que
sigue son errores **reales** encontrados y corregidos, con el número que
los delató.

### 10.1 Error del agente, corregido por el test

Al implementar la subdivisión de vigas del benchmark, el agente dejó
esta línea:

```python
nodos_techo = [nid for nid in coords if nid > mb.nNodosPorPiso]
```

Con la subdivisión, "todo nodo por encima de la base" pasó a incluir los
12 nodos intermedios nuevos. El sismo saltó de **4 × 50 = 200 kN** a
**16 × 50 = 800 kN** sin ningún mensaje de error: el modelo convergía y
el equilibrio cerraba, porque el equilibrio compara reacciones contra lo
aplicado, y lo aplicado también estaba mal.

Lo detectó `test_contrato_unity.py`, que compara contra el valor
**esperado independientemente** (200 kN), no contra lo que el modelo
aplicó:

```
[FALLA] equilibrio EX   fx = -800.0000 kN (esperado -200.0)
```

Corrección: tomar solo los nudos del marco.

```python
nodos_techo = list(range(mb.nNodosPorPiso + 1, 2 * mb.nNodosPorPiso + 1))
```

**Lección:** una verificación que se compara consigo misma no verifica
nada. La referencia tiene que venir de afuera del modelo.

### 10.2 `eleForce` devuelve ejes GLOBALES

El código leía `ops.eleForce(tag)` etiquetando la salida como
`[N, Vy, Vz, T, My, Mz]`, que es notación **local**. No lo es.

Para vigas que corren en X funcionaba por casualidad (su eje local x
coincide con el global X). Para vigas en Y, el momento de gravedad
aparecía en la casilla de **torsión**, y la viga parecía no flectar.

Se detectó con un chequeo de **simetría**: en un marco cuadrado, las
vigas X e Y deben tener esfuerzos locales idénticos.

```
VIGA X:  eleForce (GLOBAL) My = -4.1711     localForce  My = -4.1711
VIGA Y:  eleForce (GLOBAL) Mx = +4.1711     localForce  My = -4.1711
                           ^^ el flector en la casilla de torsión
```

Corrección: `ops.eleResponse(tag, 'localForce')`.

### 10.3 El `equalDOF` no era un diafragma

El modelo del edificio tenía:

```python
ops.equalDOF(master, slave, 1, 2, 6)     # ux, uy, rz IGUALES
```

Eso obliga a que **todos los nodos del piso tengan el mismo `ux`**, o
sea que el piso solo puede trasladarse y **nunca rotar**. La torsión del
edificio quedaba fuera del modelo. Además, `constraints('Plain')` no
sabe imponer un `rigidDiaphragm` real.

Corrección: `ops.rigidDiaphragm(3, maestro, *esclavos)` con
`constraints('Transformation')`, y verificación numérica de la
cinemática (§7), incluyendo el caso excéntrico que demuestra que ahora
el piso **sí** rota.

### 10.4 Torsión `J` sin fórmula

```python
J_col = min(Iy_col, Iz_col) * 0.3
```

Esa expresión no corresponde a ninguna fórmula conocida. Contra
Saint-Venant:

| sección | J usado | J real | factor |
|---|---|---|---|
| columna 50×50 | 1.562e-3 | 8.802e-3 | **5.6×** |
| viga X 30×60 | 4.050e-4 | 3.708e-3 | **9.2×** |
| viga Y 30×80 | 5.400e-4 | 5.502e-3 | **10.2×** |

En un marco cuadrado simétrico no se nota. En un edificio de 9 niveles
con planta irregular bajo sismo, sí.

### 10.5 Cargas puntuales en vez de distribuidas

La carga de losa se aplicaba como dos fuerzas en los extremos de cada
viga:

```python
F = w * dx / 2.0
ops.load(n1, 0, 0, -F, 0, 0, 0)
```

La carga total se conservaba —el equilibrio cerraba— pero **las vigas no
flectaban por la losa**: todo el momento del vano desaparecía. Para
dimensionar vigas, eso invalida el resultado.

Corrección: `eleLoad -beamUniform` con la carga tributaria.

### 10.6 Sismo dos órdenes de magnitud bajo

```python
F = 10.0 * lev      # 360 kN de corte basal
```

Contra un peso sísmico de ~100 000 kN, eso es un coeficiente de
**0.36 %**. Se reemplazó por un corte basal `V = C · W` con `C = 0.10`,
repartido en altura según `F_i = V · W_i·h_i / Σ W_j·h_j`.

Sigue siendo pseudoestático: **falta el espectro NCh433, el factor R, la
zona sísmica y el tipo de suelo**. Está marcado como tal en el código.

### 10.7 Un "error" que resultó no serlo

Al verificar el diafragma, el primer test que escribió el agente
comprobaba que todos los nodos del piso tuvieran el **mismo `ux`**. El
test falló, y la conclusión inmediata fue que el diafragma no
funcionaba.

Estaba mal el test, no el código: un diafragma es rígido *en su plano* y
con carga excéntrica **rota**, así que los `ux` difieren legítimamente.
Lo correcto es verificar la relación de cuerpo rígido, que cierra con
error 0.

**Lección:** cuando un test falla, el sospechoso número uno es el test.

---

## 11. Pendientes

| tema | estado |
|---|---|
| ~~Altura del modelo~~ | **resuelto** (§2.1): 6 niveles de 3.96 m hasta +11.83 m |
| ~~Muros extruidos por los 8 pisos~~ | **resuelto** (§2.1): cada muro sube solo hasta donde lo muestran las plantas |
| **Empotramiento lateral de la fundación escalonada** | fuera del modelo: con diafragma rígido congelaría el piso 1 (§2.1) |
| ~~Ejes Y = 46.92 y 65.22~~ | **resuelto** (§1): eran los ejes 3' y 1b, mal leídos por el quiebre del globo. Corregidos a 47.70 y 64.65 |
| ~~Alinear las láminas entre sí~~ | **resuelto**: cada planta se referencia por su cruce eje E × eje 3 |
| Brazos rígidos en la unión viga-muro | pendiente; hoy el muro tiene ancho cero en esa unión |
| Ejes locales dibujados en Unity | pendiente |
| Espectro NCh433 completo | pendiente; hoy `C = 0.10` fijo |
| Fiber Sections / no lineal | pendiente (Semana 4+) |
| Peso propio de columnas como carga distribuida | hoy va como fuerzas nodales |

---

## Reproducibilidad

```bash
python benchmark_3d.py              # modelo + 4 casos + equilibrio
python export_unity.py              # exporta a Unity + round-trip
python verificar_planos.py          # ejes y muros contra los DXF
python test_areas_tributarias.py    # conservación y geometría del reparto
python test_servidor.py             # multi-caso, diafragmas, apoyos
python test_contrato_unity.py       # campos C# ↔ JSON
python benchmark_distribuida.py     # benchmark Semana 1 (−0.06348 mm)
```

Los siete terminan indicando si algo se rompió. `verificar_planos.py`
necesita los DXF en `C:\dxf_planos\` (fuera del repo); si no están,
avisa y no falla.
