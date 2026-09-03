# Modelo estructural del edificio LT2

Modelo 3D lineal elástico en OpenSees, armado **entero desde los planos de
cálculo** `2024_22` (M. Kupfer C., octubre 2024). Nada de la geometría ni de las
cargas está escrito a mano en el código.

```
DWG ──► DXF ──► geometria_lt2_2024_22.json ──► modelo OpenSees
        (AutoCAD headless)   (ingestor)          (modelo_lt2.py)
```

---

## El modelo

| | |
|---|---|
| Nodos | 247 |
| Columnas | 40 |
| Muros (columna ancha) | 45 |
| Vigas | 230 (2 son dinteles supuestos) |
| Brazos rígidos | 115 (a muros y entre muros, todos en ángulo recto) |
| Apoyos empotrados | 17 (en z = −7.97) |
| Diafragmas rígidos | 5 |
| **Carga total, caso G** | **34 011 kN** |
| **Error de equilibrio** | **8.7 × 10⁻⁸ kN** |

**Niveles** (m): −7.97 (base) · −4.01 · −0.05 · +3.91 · +7.87 · +11.83.
Altura entre pisos constante de **3.96 m**, confirmada por las 6 elevaciones.

### Área de losa por piso

Los cinco pisos dan el mismo número, y eso no estaba puesto a mano: la planta
tipo y la planta de techo son láminas distintas, leídas por separado.

| Nivel | Área | Paños | A vigas | A muros | Conservación |
|---|---:|---:|---:|---:|---:|
| todos | 496.87 m² | 17 | 495.93 | 44.47 | 5 × 10⁻⁴ m² |

### Deformada bajo G

| Nivel | Mediana | Máximo |
|---|---:|---:|
| −4.01 | 0.73 mm | 4.51 mm |
| −0.05 | 1.28 mm | 5.45 mm |
| +3.91 | 1.54 mm | 6.15 mm |
| +7.87 | 1.61 mm | 6.61 mm |
| +11.83 | 1.55 mm | 6.72 mm |

Ningún nivel queda sin aprobar y no hay ningún nodo que baje más de 10 veces la
mediana de su piso.

---

## De dónde sale cada dato

| Dato | Valor | Fuente en el plano |
|---|---|---|
| Ejes | 18 con nombre (10 en X, 8 en Y) | burbujas `RLE-EJE` |
| Niveles | 7 cotas | las 6 elevaciones coinciden en las 7 |
| Hormigón | **G35_10, f'c = 35 MPa** | nota de la lámina 100 |
| Pilares | 0.70 × 0.70 | medidos, confirmados por `P.70x70` |
| Muros | e = 0.25 / 0.30 / 0.60 | medidos, confirmados por `M.H.A. e=…` |
| Vigas | 0.60/0.80, 0.40/0.80, 0.30/0.80 | ancho medido, alto leído de `V. 60/80` |
| Losa | e = 0.15 m | atributo `ESP` de los 22 bloques `losa-ne` |
| Cargas plantas tipo | **G = 6.30 · Q = 4.90 kN/m²** | lámina 700, plano de cargas |
| Cargas cielo piso 4 | **G = 5.71 · Q = 2.94 kN/m²** | lámina 700, plano de cargas |

Los espesores de muro medidos geométricamente coinciden **uno a uno** con los
rótulos `M.H.A. e=…`: `e=25` ×4, `e=30` ×3, `e=60` ×2 — 9 muros, 9 rótulos. Las
dos cifras vienen de fuentes distintas del plano, así que es una verificación
cruzada real. (Los `e=20` que aparecían antes eran los muros de independencia de
la rampa; ver el punto 8.)

---

## Cómo se reparte la carga de losa

Por **áreas tributarias a 45°**, el mismo criterio del P1. La diferencia es que
en el P1 los paños venían dados por una grilla regular de ejes; acá la planta es
irregular y **los paños hay que encontrarlos**: son las caras del grafo plano que
forman las vigas de cada piso (`src/panos.py`).

### Qué significa "bisectriz a 45°"

Trazar bisectrices desde las esquinas es la construcción de dibujo. Lo que
significa es: **cada punto de la losa carga al lado que tiene más cerca**. La
frontera entre dos lados es el lugar de los puntos equidistantes de ambos —
para dos rectas, su bisectriz; en una esquina recta, una recta a 45°.

Escrito así el reparto se **calcula** en vez de dibujarse. La región del lado `i`
es el paño recortado por un semiplano por cada otro lado `j`:

```
dist(x, lado i)  ≤  dist(x, lado j)
```

y como dentro de un paño convexo la distancia a un lado es la distancia a su
recta, cada condición es un semiplano. Recortando con todos queda un polígono
exacto — y en un rectángulo salen exactamente los dos **trapecios** de los lados
largos y los dos **triángulos** de los cortos, con las áreas de las fórmulas
cerradas del P1:

| paño 10.00 × 3.34 | viga larga | viga corta |
|---|---:|---:|
| fórmula del P1 | 13.9111 m² | 2.7889 m² |
| polígono recortado | 13.9111 m² | 2.7889 m² |

Eso no hay que creerlo: lo comprueba `verificar_lt2.py`. **El área que se carga
sale del polígono**, no de una fórmula aparte, así que lo que se dibuja y lo que
se calcula no pueden decir cosas distintas.

En el visor: activar "Áreas tributarias" y hacer clic en una viga.

### Por qué no repartir por largo de viga

Los dos repartos suman lo mismo (33.4 m²) — **por eso el equilibrio global cierra
igual de bien con cualquiera de los dos**. Pero repartir por largo daría 12.52 y
4.18 m²: sobrecarga la viga corta un **50 %**. Es el mismo tipo de error que el
reparto 50/50 de la Semana 1, y el equilibrio no lo detecta nunca.

### Los muros también son borde de paño

En la zona nororiente de esta planta no hay ninguna viga: la losa se apoya
directo sobre los muros. Como un muro es *una* columna ancha en su baricentro,
su área tributaria va como carga **puntual** en su nodo, que es estáticamente
equivalente. Son 44.47 m² de los 496.87 del piso.

---|---:|---:|
| **45°** | 13.91 m² | 2.79 m² |
| por largo de viga | 12.52 m² | 4.18 m² |

Los dos repartos suman lo mismo (33.4 m²) — **por eso el equilibrio global cierra
igual de bien con cualquiera de los dos**. Pero repartir por largo sobrecarga la
viga corta un **50 %**. Es el mismo tipo de error que el reparto 50/50 de la
Semana 1, y el equilibrio no lo detecta nunca.

---

## Verificaciones (`verificar_lt2.py`) — 36 checks, todas pasan

| Verificación | Resultado |
|---|---|
| Equilibrio global `ΣR = ΣF` | error **8.7 × 10⁻⁸ kN** sobre 34 011 kN |
| Secciones contra cálculo a mano | A, Iy, Iz, J exactos |
| `J` de Saint-Venant ≠ `min(Iy,Iz)·0.3` | 1.14 × 10⁻³ vs 2.03 × 10⁻⁴ (5.6×) |
| Orientación de muros: inercia fuerte en el eje correcto | los 45 |
| Razón `I_fuerte/I_débil` | hasta **1011** |
| Linealidad: 2×carga → 2×desplazamiento | error **0.00** |
| Diafragma: `ux_i = ux_m − rz·(y_i − y_m)` | error **0.00 m** |
| El diafragma **permite giro** (no es un `equalDOF`) | 1.0 × 10⁻⁴ rad |
| Insensibilidad al factor del brazo (×25/×100/×400) | varía **0.10 %** |
| Cargas contra el plano de cargas | los 4 valores calzan |
| Áreas tributarias reproducen las fórmulas del P1 | sí |
| Σ áreas tributarias = área de los paños | error **0 m²** |
| Viga por viga: `w·L = q·A` | peor error **3 × 10⁻¹⁴ kN** |
| Los polígonos tributarios **teselan** cada paño | error **0.0000 m²** en los 17 |
| Cada cara del grafo tiene su rótulo de losa en el plano | 22 rótulos en 17 caras |

---

## Los seis que se encontraron mirando números

Todos producían un modelo que **corría y devolvía números**.

**1. Un muro colgando entre +7.87 y +11.83.** La lámina 102 dibuja un muro que la
101 no tiene, y quedó un tramo vertical sin nada debajo. UZ = −1.2 × 10¹⁴ mm.
LAPACK no siempre falla con la matriz singular: a veces devuelve un número
enorme, que es peor, porque parece un resultado.

**2. Distancia perpendicular dividida de más por el largo del eje.** `dx, dy` ya
eran unitarios. Un muro a 20 m de una viga "medía" 0.26 m: aparecían elementos de
**20 m que no existen en el plano** y una flecha de 678 mm donde el piso daba 4.

**3. Cruces de viga recortados al extremo dibujado.** El eje de una viga se corta
en la **cara** de la viga a la que llega. Al recortar el cruce quedaban dos nodos
a 0.42 m sin fundirse, y las dos vigas **no se conectaban aunque en el plano se
cruzan**: 100 tramos perdidos. Un modelo de barras une los ejes en el cruce.

**4. Vigas estiradas hasta el baricentro del muro.** Una viga que llega a la punta
de un muro de 8 m se estiraba 4 m. Se reemplazó por un **brazo rígido**, que es lo
que físicamente hay ahí: el propio muro.

**5. Trozos de una misma viga sin unir.** Una viga larga no se dibuja de una pieza.
En la lámina 102 la viga de fachada salió en cuatro trozos con huecos de 0.75 a
1.10 m, y los del medio **terminaban en el aire**: 204 mm de flecha. En la 101 la
misma viga también sale en trozos, pero ahí los huecos caen justo donde la cruza
una viga transversal, así que se conectaban igual y no se notaba nada — **el mismo
defecto, visible en una lámina e invisible en la otra**.

**6. Agrupar por redondeo en vez de por tolerancia.** Un trozo dibujado con ángulo
−0.00006° cae en 179.99994 al aplicar módulo 180, y terminaba en otra casilla que
su continuación de +0.00006. Diez trozos de la misma viga de techo quedaron en dos
grupos alternados y no se unió ninguno.

---

## Los cuatro que se vieron recién al abrir el visor

Los seis de arriba se encontraron mirando números. Estos cuatro **sólo se vieron
al mirar el modelo en 3D**, y los cuatro daban un modelo que corría, cerraba
equilibrio a 10⁻⁷ y pasaba todas las verificaciones de entonces.

**7. Un edificio que no es este.** La lámina 102 dibuja, pasada la junta, tres
pilares en `x = 43.15` y sus vigas. Uno de los rótulos dice `+V.I. 15/70
(2ª ETAPA)` y a los 60 cm hay un texto que dice `ETAPA ANTERIOR`. Son del cuerpo
vecino. El recorte por *toda* la malla de ejes no los sacaba, porque tienen ejes
propios (`D'`, `E'`) y caen dentro de ella.

La junta la marca el dibujo solo: la cara este del LT2 está en `x = 42.702` y la
cara oeste del otro cuerpo en `x = 42.802`. **Esos 10 cm son la junta de
dilatación** que la lámina 700 rotula siete veces.

**8. Una rampa modelada como torre de 20 m.** Entre los ejes `8A` y `8B` las tres
plantas dibujan un cuerpo con `i = 52.46 %`, `i = 52.62 %`, `N.S.M. = VAR`,
`N.O.G. = VAR` y cotas −7.39, −6.97, −5.15, −4.73, −3.23, −2.81, todas de la
elevación 302. Es la **rampa de acceso al subterráneo**: una losa inclinada sobre
muros de independencia que no pasa del subterráneo. La lámina de techo ni
siquiera tiene los ejes 8A y 8B.

La regla de continuidad vertical la subía hasta +11.83, así que en el visor
aparecían **cuatro torres de 20 m paradas al lado del edificio**, sin una sola
viga que las uniera a nada.

Las dos cosas se arreglan igual: la ventana de recorte pasó de ser *toda* la
malla de ejes a ser **cuatro bordes declarados** (`ventana.modo =
"ejes_nombrados"`), cada uno un eje con nombre o —para la junta, que no tiene
eje— una coordenada. Es el mismo mecanismo con el que dos personas se reparten
un juego de planos: cada una declara los ejes que acotan su cuerpo.

**9. `PASADA 45/30`.** En el techo, seis vigas terminaban en el aire, con 54 mm
de flecha contra 2 mm de mediana del piso. Los huecos medían 1.72, 1.88, 1.98,
2.08, 2.23, 2.26 y 2.28 m, y el tope para unir trozos colineales era 1.5 m.

En el hueco está escrito `PASADA 45/30`: una perforación de 45 × 30 cm por donde
bajan ductos. La viga **no** se interrumpe; el dibujo corta la línea para mostrar
el paso. Además el rótulo `45/30` era el que hace tres semanas contaminaba las
secciones de viga: el mismo texto, dos problemas distintos.

El tope pasó a ser una opción del perfil (`vigas.gap_colineal`), porque depende
de cómo dibuja cada calculista.

**10. Caras partidas que se tiraban por cortas.** Una cara no se dibuja como un
segmento: se dibuja como polilínea, y sale partida en cada vértice. La cara oeste
del techo llega en cuatro trozos de 0.28, 1.55, 0.46 y 3.39 m — una sola recta
de `y = 12.754` a `y = 18.729`.

El emparejamiento descartaba las caras más cortas que `largo_min = 1.0 m`
**antes** de emparejar, así que los trozos de 0.28 y 0.46 desaparecían y la viga
de fachada del techo arrancaba 1.09 m más arriba, en el aire, a un metro del muro
donde en realidad apoya.

Ahora las rectas se rearman primero (`muros.fusionar_colineales`) y recién
después se descarta por largo. En la lámina 102 se rearmaron **81 trozos**.
Fusionar no inventa nada: dos trozos colineales que se tocan **son** una recta.

**11. El 15 % de la losa que no cargaba a nadie.** Un paño existe sólo si su
borde **cierra**. Donde no hay viga, el borde es un muro — y un muro no termina
donde termina una viga: el muro este llega a `y = 10.58` y la viga de fachada a
`y = 10.93`, media viga de diferencia. Además el muro este viene partido por las
puertas: 10.58–18.53, hueco de 2.40, 20.93–23.75, hueco de 0.30, 24.05–26.73.

Con el borde abierto, la cara no se encuentra y **su carga desaparece**. Eran
75 m² por piso, 15 % de la planta, unos 2 300 kN. Y desaparecían en silencio:
el equilibrio compara contra la carga **aplicada**, así que seguía cerrando a
10⁻⁷ con el piso incompleto. Es exactamente el tipo de error que el equilibrio
no puede ver.

`panos.cerrar_borde()` hace dos cosas, las dos auditadas: funde las puntas que
están a menos de 0.45 m (la misma esquina dibujada por dos elementos distintos:
21 nodos por piso) y puentea los huecos **colineales** de hasta 3 m (los vanos:
1 por piso, de 2.58 m). Lo que no se puede cerrar se cuenta y se queda abierto:
queda 1 punta suelta por piso, el muro del núcleo que termina en medio del hall.
El área por piso pasó de 427.85 a **500.18 m²**.

**12. Las vigas llegaban a la CARA del pilar, no a su eje.** El plano dibuja la
viga terminando en la cara del pilar — ahí termina el hormigón de la viga. El
modelo ponía el nodo ahí y un brazo rígido de 0.35 m hasta el eje. Es más exacto
(es el *rigid end offset*), pero en el visor la viga se ve **cortada a 35 cm de
la columna**, y en el plano llega.

Ahora, contra un **pilar** la viga se estira hasta su eje: es la convención de
cualquier modelo de barras y la luz de cálculo es la distancia entre ejes.
Contra un **muro** sigue el brazo rígido, porque ahí el baricentro puede estar a
4 m y estirar la viga le inventaría vano.

De paso apareció otro: al estirarse ese extremo hasta el pilar, el brazo que
salía de él quedaba **colgando del muro sin unir nada** — cinco palos saliendo
de la nada en el visor. No rompía el análisis (el muro llega al suelo, así que
la poda no los veía). Ahora un brazo sin viga en su punta se descarta y se
cuenta.

Brazos de viga a muro: 65 → 30, y los 30 que quedan son todos de muro
(0.74 a 3.63 m).

## Los cuatro que se vieron abriendo el visor y comparando con el plano

Tres de los cuatro **no eran del modelo sino del visor**: el cálculo estaba
bien y lo que se dibujaba no correspondía. Ese es su propio tipo de error, y es
peligroso al revés que los otros — invita a "arreglar" un modelo que está sano.

**13. Todos los muros dibujados girados 90°.** En un muro, `vecxz` es la
**normal** al muro — es lo que pone la inercia fuerte donde corresponde. El C#
lo leía como si apuntara *a lo largo*, así que dibujaba cada muro con el largo
y el espesor intercambiados. Se veía como dos síntomas distintos: el núcleo de
ascensores atravesado, y el muro de 7.95 m del eje D "desaparecido" — en
realidad dibujado metido 7.95 m hacia adentro de la planta, cruzándola.

Arreglo: Python exporta `dir_largo` (hacia dónde corre el largo del muro en
planta) y Unity lo **dibuja**, no lo deduce. Es la misma regla que ya regía para
los ejes locales, aplicada a un campo al que se le había escapado.

**14. Las esquinas de muro, vacías.** Un muro se idealiza como *una* columna
ancha en su baricentro. Dos muros perpendiculares que en la obra son **una sola
pieza de hormigón en L** quedaban como dos barras separadas 1.5 m con nada entre
medio, y cada una trabajando sola.

Ahora se unen con un brazo rígido cuando se tocan de verdad: dos puntas son la
misma esquina si están más cerca que **la semisuma de los dos espesores**. No es
una tolerancia inventada — es la condición de que los dos muros se solapen
físicamente. Encontró 6: las dos del poniente (e=60 con e=30) y las cuatro del
núcleo, incluida la puerta de 0.30 m que parte en dos el muro oriente: sobre una
puerta hay dintel y el muro sigue.

**15. Cuadrados verdes flotando en cada piso.** Los **nodos maestros de
diafragma**. El visor los pintaba como apoyos porque preguntaba "¿tiene alguna
restricción?" — y el maestro siempre tiene tres (`uz, rx, ry`), porque el
diafragma no toca esos GDL y sin restringirlos la matriz sale singular. Existen
y están bien; no son fundaciones. Ahora la capa de apoyos salta los nodos
auxiliares.

**16. "Escaleras" grises flotando en el aire.** Los brazos rígidos, exportados
como `muro`. El dibujo de muro usa la distancia entre nodos como **altura**, así
que un brazo horizontal de 3.6 m salía como una plancha de 3.6 × 3.6 m parada de
canto. Y con "perfiles reales" activado se dibujaban con su sección real, que es
de **4 × 4 m**: es un artificio numérico (la sección de viga mayor escalada por
`FACTOR_BRAZO`) y no tiene por qué verse. Ahora tienen tipo propio `brazo`, van
como línea fina y tienen su toggle.

**17. `ver.ps1 -Recompilar` no recompilaba.** Mandaba `app --forzar`, y
`--forzar` sólo lo entiende el modo `build`; el modo `app` lo ignoraba en
silencio. O sea: se editaba un `.cs`, se corría `-Recompilar`, y se abría **la
app vieja sin un solo aviso**. Es el mismo patrón que el resto de esta lista —
una herramienta que contesta algo plausible cuando debería contestar un error.

**18. Un muro cortado por el muro que topa contra él.** El plano dibuja la
esquina poniente como una **T**: el muro de e=60 corre de `y = 9.84` a `12.75` y
el de e=30 topa contra su costado. En el DXF su cara exterior sale entera, pero
la interior viene cortada exactamente por los 0.30 m del que llega: 0.79 + hueco
+ 1.83. Los 0.79 se descartaban por medir menos que `largo_min`, y el muro salía
de **1.82 m en vez de 2.92** — una L donde el plano dibuja una T.

Ahora se puentea ese hueco, **pero sólo si uno de los dos lados es corto**. Eso
distingue dos cosas que se parecen y no lo son:

| | qué es | qué se hace |
|---|---|---|
| un trozo corto + hueco + trozo largo | un **cruce**: otro elemento corta la cara | se unen: es un solo muro |
| dos trozos largos + hueco | una **puerta** | no se tocan: son dos muros, unidos por el dintel |

El tope del puente es `espesor_max`, porque el hueco que abre un cruce es como
mucho el espesor del que cruza. La cobertura de muros subió de 94.3 % a
**98.5 %**, y la puerta de 0.30 m del eje D siguió siendo dos muros.

De paso: el criterio de esquina comparaba **punta contra punta**, que sólo
detecta una L. En una T la punta de un muro topa contra el **costado** del otro.
Ahora se mide punta contra cuerpo.

**19. Cincuenta pares de nodos dobles, a 30 cm.** El dibujo corta una viga en la
**cara** de aquello contra lo que llega, no en su eje. La viga que baja por el
eje C arranca en `y = 11.23`, que es la cara de la viga de fachada cuyo eje está
en `y = 10.93`. El cruce de ejes ya ponía un nodo en 10.93, pero además se
conservaba el extremo dibujado: dos nodos a 0.30 m unidos por un **tramo de viga
de 30 cm que no existe en ninguna parte**.

Eran 50 pares por modelo. Ahora el extremo dibujado se descarta si hay otro corte
—un ancla o un cruce de ejes— a menos de `MARGEN_CRUCE` de él; si no hay ninguno,
es un extremo real y se conserva. **50 nodos y 50 elementos menos.**

**20. Brazos rígidos que no hacían falta.** El brazo existe para no inventar
vano: una viga que llega a la punta de un muro de 8 m se estiraría 4 m. Pero en
un muro **corto** el baricentro queda a un paso. En los muros de 1.45 m de las
esquinas el brazo medía 0.74 m, y sólo agregaba un nodo y un elemento. Medido:

| | UZ máximo |
|---|---:|
| con brazo | 6.6555 mm |
| estirando la viga | 6.6493 mm |

**0.09 % de diferencia.** Se elige estirar por debajo de 0.80 m: mismo resultado
con 10 nodos y 10 elementos menos. Por encima de ese valor sigue el brazo.

**21. La mitad de la losa no se veía cargando a nadie.** El visor dibuja las
áreas tributarias **por elemento**, y sólo se exportaban las de las vigas. Los
paños que descargan sobre un **muro** (51 m² por piso, el bloque nororiente) y
los que descargan sobre un **brazo** (los del núcleo) quedaban como huecos
blancos. La carga estaba aplicada y el equilibrio cerraba; simplemente no se
veía, y quien mirara habría concluido que faltaba.

Ahora se exportan las tres: viga, brazo y muro. En un muro, `luz` es su largo y
`w` la carga repartida sobre él — misma resultante que el modelo aplica como
carga puntual en su baricentro. La planta queda cubierta entera salvo el hueco
del ascensor, que no tiene losa.

**22. La unión de dos muros iba en diagonal, y eso cortaba la esquina.** El
problema no era que faltara la unión: era **por dónde iba**. Al unir dos
baricentros con un brazo directo, el brazo cruza la esquina en diagonal.
Estructuralmente da casi lo mismo, pero el borde del paño pasa a ser esa
diagonal: el área tributaria de la esquina sale triangulada en vez de
rectangular, y el núcleo de ascensores queda escalonado.

Lo que hay ahí de verdad es hormigón **a lo largo de los dos muros** hasta donde
se cruzan sus ejes. Ahora se pone un nodo en ese cruce y se va con dos brazos:

```
baricentro A ──► cruce de ejes ──► baricentro B
```

Los dos corren a lo largo de su muro, el borde gira en ángulo recto y la esquina
queda rectangular.

La regla se generalizó a **cualquier par de elementos verticales cuyas huellas se
solapen**, no sólo muro con muro:

| par | por dónde pasa la unión |
|---|---|
| muro + muro no paralelos | el cruce de sus ejes |
| pilar + muro | el pilar proyectado sobre el eje del muro |
| ejes paralelos, o dos pilares | brazo directo (ya va sobre el eje) |

El caso pilar + muro no era un detalle: el pilar de la esquina nororiente está
embebido en la punta del muro de fachada, y sin esa unión el paño de 45 m² de
ese bloque no cerraba.

**23. Dos aristas superpuestas hacen desaparecer un paño entero.** El brazo
directo entre los dos tramos del muro oriente (los de la puerta) pasaba **por
encima** del nodo de esquina que los une al muro transversal. Dos aristas
colineales superpuestas rompen la búsqueda de caras, y no de una forma que se
note: el recorrido decide por dónde seguir ordenando los vecinos **por ángulo**,
y dos vecinos colineales tienen el mismo ángulo. Al elegir el equivocado el
recorrido se salta un nodo, **la cara interior se funde con la exterior** y
desaparece — 45 m² sin ningún error.

Ahora todo brazo se parte en los nodos que caen encima de él.

**24. Dos lados sobre la misma recta reclamaban los dos la franja entera.** Un
muro entra al paño **partido en tramos** — por su baricentro, por un nodo de
esquina, por una puerta. Dos tramos colineales están sobre la misma recta, así
que la distancia a la recta no los distingue, y sin desempate cada uno se
quedaba con toda la franja: los polígonos de un paño de 37.8 m² sumaban **67.3**,
y en el caso peor 174 m² sobre 45.6.

El desempate es la distancia **a lo largo** de la recta: el punto carga al tramo
que tiene más cerca, y la frontera es la perpendicular en la mitad del hueco.
Ahora los polígonos **teselan exactamente** cada paño, convexo o no: error
`0.0000 m²` en los 17.

**25. La caja de ascensores se recorría como una ranura.** La caja tiene tres
muros en U y el cuarto lado es el acceso. Con el vano abierto, el borde del paño
**entra en la caja y vuelve a salir**: el recorrido pasa dos veces por las mismas
aristas y el reparto se rompe.

Se declaran dos **dinteles supuestos** en el perfil (no en el código): el del
acceso a la caja (2.65 m) y el del vano de la fachada oriente (2.40 m). Las
láminas no los dibujan; un vano de ese ancho entre dos muros de hormigón lleva
dintel, y sin ellos el bloque nororiente entero —45 m² por piso— no cerraba como
paño. Aparecen como supuesto en la auditoría y se sacan editando sólo el perfil.

**26. El hueco del ascensor cargaba losa.** Cerrada la caja, queda una cara de
7.86 m² perfectamente cerrada — y adentro no hay losa: es por donde sube el
ascensor. Cargarla serían 50 kN por piso inventados.

El criterio para descartarla no lo pone quien programa: **lo pone el plano**.
Cada paño viene rotulado con un bloque `losa-ne` con su nombre (`0100`, `0101`,
…) — el mismo del que ya se leía el `e=15`. Una cara con rótulo lleva losa; una
cara sin ninguno, no.

Y eso, de paso, es una **comprobación cruzada** que antes no existía: la
geometría sale de las líneas de muros y vigas, y los rótulos son otra fuente del
mismo plano. Los **22 rótulos caen en 17 caras**, ninguno a más de 1 m de la
suya, y la única cara sin rótulo es el hueco del ascensor. (Algunos rótulos están
escritos fuera del edificio con su línea de referencia apuntando adentro, así que
cada uno se asigna a la cara más cercana, no a la que lo contiene.)

**27. El perímetro del edificio salía en zigzag.** Una fachada no es un solo
elemento: hay una viga de 0.60 de ancho a lo largo de casi todo el frente y, en
las esquinas, un muro de 0.30. Los dos comparten la **cara exterior** del
edificio — en el LT2, `y = 10.63` — pero como tienen anchos distintos sus **ejes**
no coinciden: la viga en 10.93 y el muro en 10.78, **15 cm de diferencia**.

Cada uno en su eje, el perímetro queda con un escalón de 10 a 15 cm en cada
esquina, el borde de los paños se quiebra y las áreas tributarias terminan en
astillas diagonales.

Ahora los elementos paralelos cuyos ejes están a menos de `0.20 m` se llevan al
eje del **más largo** — el que manda la línea de fachada. Movió 4 muros, el mayor
0.15 m; mover un muro de 1.45 m unos 15 cm no cambia nada estructural y a cambio
el perímetro queda recto. La tolerancia está en el perfil y lo que se movió queda
en la auditoría.

Y para la viga que llega **perpendicular** a un muro, su nodo va ahora en el
**eje** del muro, no en su cara: la viga de fachada sur terminaba en `x = 42.45`
y el eje del muro oriente está en `42.577`, así que el brazo salía inclinado
13 cm y la esquina quedaba en diagonal. Sólo se acepta si el corrimiento va **a
lo largo** de la viga; si la moviera de lado le haría un codo.

**28. Dos errores que se tapaban entre ellos.** Al enderezar el perímetro
desaparecieron los dos paños de esquina (15.6 m² cada uno) y aparecieron huecos
blancos. Eran dos cosas distintas:

*Fundir dos nodos que ya estaban unidos por un elemento.* El baricentro del muro
poniente (`11.302, 11.297`) y el cruce de los dos ejes (`11.302, 10.929`) quedan
a 0.368 m y los une un brazo. El cierre del borde los fundía por cercanía — y
eso **borra el brazo**: el borde pasaba de dos tramos en ángulo recto a una
diagonal. Ahora nunca se funden dos nodos adyacentes: esos no son la misma
esquina dibujada dos veces, son los dos extremos de un elemento que existe.

*Un pedazo de arista que olvida de dónde viene.* Al partir una arista en los
nodos que caen encima —lo que hay que hacer para no dejar aristas superpuestas—
los pedazos perdían el elemento del que salieron, así que su polígono tributario
se descartaba. De ahí los huecos blancos. Ahora cada pedazo **hereda** la arista
de la que salió.

Con las dos cosas arregladas: **17 paños, los polígonos teselan con error
`0.000000 m²`, y 16 de los 17 son convexos** (antes 14).

---

## Limitaciones — declaradas, no escondidas

1. **Se supone continuidad de muros y pilares hacia arriba.** Una lámina de losa
   no vuelve a dibujar los muros que ya venían de abajo.

2. Quedan **16 m² por piso** (3 % de la planta) entre el eje de las vigas de
   fachada y el eje de los muros perimetrales. Está medido y contado.

3. La fundación se reemplaza por empotramiento en z = −7.97.

4. Lineal elástico, sin fisuración.

5. La losa no se modela como placa: sólo baja su carga.

6. Falta la **carga lineal** del plano de cargas (tabiques y antepechos:
   SC = 100 y 200 kgf/m, PM. ADIC. = 1500 kgf/m sobre vigas).

7. Los polígonos tributarios de 3 de los 19 paños son **aproximados**: esos
   paños no son convexos, y ahí la distancia a la recta de un lado deja de ser
   la distancia al lado. El área se reescala para que igual sume la del paño, o
   sea que la carga se conserva exacta aunque el dibujo no lo sea. Está contado
   en la auditoría (`metodos: bisectrices / bisectrices_aprox`).

## Sobre unir los dos edificios

La lámina 700 rotula **`JUNTA DE DILATACIÓN 10 cm`** siete veces, y las láminas
101 y 700 hablan de **`ETAPA ANTERIOR`** y **`2ª ETAPA`**. Decisión tomada: los dos
cuerpos van **estructuralmente separados**.

Ahora la junta además está **medida**: la cara este del LT2 está en `x = 42.702`
y la cara oeste del otro cuerpo en `x = 42.802`. El modelo se corta en
`x = 42.75`, declarado en `perfiles/lt2_2024_22.json` → `ventana.xmax`.

Al unir los modelos **no comparten nodos**: son dos estructuras independientes
puestas una al lado de la otra, cada una con sus propios apoyos y diafragmas. Lo
único común es el sistema de coordenadas.

El mecanismo para ponerlas en el mismo sistema ya existe:
`src/planos/alineacion.py` registra por ejes con nombre común, y si no hay ejes
compartidos acepta un desplazamiento declarado a mano.

Y el mecanismo para **repartirse el trabajo** también: `ventana.modo =
"ejes_nombrados"` deja que cada perfil declare los cuatro ejes que acotan su
cuerpo. Los dos ingestores leen las mismas láminas y cada uno se queda con lo
suyo, sin tocar el código.
