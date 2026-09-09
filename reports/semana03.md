# Semana 3 — Carga viva, sismo, superposición y capacidad HA

**Edificio de Ingeniería, Universidad de los Andes**
Grupo 7 · Laboratorio estructural digital

Todos los números de este informe salen de correr los scripts de
`semana03/` y `comun/` sobre los modelos de `data/modelo/`. Ninguno está
escrito a mano. Para reproducirlos:

```bash
python semana03/lab_semana03.py ingenieria                   # Partes A, B, C
python comun/capacidad.py ingenieria 18 --pm --mphi --dibujo  # Parte D
python semana03/demanda_capacidad.py ingenieria 18 --grafico --mphi
python semana03/verificar_rc.py ingenieria 18
```

El laboratorio corre igual sobre `lt2` y `conjunto`. Los tres cierran.

---

## 1. Sobre qué modelo

El modelo es el de la Semana 2: 326 nodos, 559 elementos (82 columnas,
56 muros, 301 vigas, 104 brazos rígidos, 8 pilares y 8 diagonales
metálicos), 5 diafragmas rígidos y los casos G, Q, EX y EY. No se
reconstruye ni se modifica. Lo que la Semana 3 agrega es **cómo se usa**:
los casos Q, EX y EY se construyen en memoria con los parámetros que dicte
el profesor, se resuelven con el mismo motor de OpenSees que usa todo el
proyecto (`comun/servidor_opensees.py`) y se verifican.

Los parámetros están en `semana03/parametros.json` y cualquiera se
sobreescribe por línea de comandos. En este informe valen `q_Q = 2.0
kN/m²`, `Cs = 0.10`, `W = G + 0.5 Q`, patrón triangular invertido y la
combinación `1.0 G + 0.5 Q + 1.0 EX`.

## 2. Parte A — Carga viva

### Cómo se construye Q

El caso Q del modelo dice **por dónde** baja cada carga: repartida sobre
una viga, o puntual en la cabeza del muro que recibe la losa. Eso se
conserva. Lo que se reemplaza es la intensidad: cada elemento pasa a
recibir `q_Q · A_i`, con el área tributaria `A_i` que trae sellada.

No se escala el caso entero por un factor. Hacerlo habría estado bien en
este edificio, cuyo plano trae una sola intensidad, pero no en el LT2:

| edificio | intensidades en el caso Q del modelo |
| --- | --- |
| Ingeniería | 2.0000 kN/m² en las 301 cargas |
| LT2 | 4.9033 kN/m² en 194 cargas y **2.9420 en 49** (500 y 300 kgf/m² del plano de cargas: pisos y techo) |
| conjunto | las tres anteriores a la vez |

Un factor único sobre el LT2 dejaba el techo a 1.30 kN/m² y los pisos a
2.17, ninguno igual a `q_Q`. El enunciado pide **una** intensidad. La
reconstrucción por elemento la da exacta en los tres modelos: leída de
vuelta, el peor desvío es `2e-16`.

La construcción se detiene si una carga nodal del modelo no tiene un
elemento con área que la explique, o si un elemento con área no baja por
ningún lado. En los tres modelos cierra: los 39 muros del LT2 que reciben
losa la bajan como carga puntual en su nodo superior, y los 39 quedan
emparejados con las 39 cargas nodales del caso.

### Qué se verifica

`sum(Q) = q_Q · A` es una identidad: así se construyó. Lo que sí dice algo
es que la carga llegue **entera al suelo**:

| | Ingeniería | LT2 | conjunto |
| --- | --- | --- | --- |
| elementos con losa | 301 | 243 (204 repartidos, 39 puntuales) | 544 |
| área tributaria | 4320.6505 m² | 2515.8939 m² | 6836.5444 m² |
| `q_Q · A` | 8641.3010 kN | 5031.7879 kN | 13673.0889 kN |
| reacciones Rz | 8641.3008 kN | 5031.7878 kN | 13673.0886 kN |
| error relativo | 2.3e-08 | 1.2e-08 | 1.9e-08 |

El reparto fino —que cada viga reciba lo que dibuja su polígono, con el
peso propio separado, piso por piso— lo revisa aparte
`comun/verificar_tributarias.py`, que sobre este edificio da `q = 2.0000`
en los cinco pisos y *TODO CALZA*.

## 3. Parte B — Sismo pseudoestático

### El patrón lo define el profesor

La fuerza lateral en cada nivel es una fracción del corte basal
`V = Cs · sum(W_i)`, con `W_i = G_i + f · Q_i` el peso sísmico del
diafragma. Cómo se reparte en altura estaba fijo en el código como
triangular invertido; ahora es un parámetro:

- `potencia`: `F_i ∝ W_i · h_i^k`, con `k = 0` uniforme, `k = 1` el
  triangular clásico, `k = 2` el límite de NCh433 / ASCE 7;
- `manual`: las fracciones que se dicten, de abajo hacia arriba.

El peso se reparte **por diafragma, no por cota**. Importa en el
conjunto, que tiene dos diafragmas por nivel —uno por cuerpo— a la misma
altura: buscar el nivel por la cota más cercana metía todo el peso en el
primero de cada par y dejaba al segundo cuerpo sin sismo (cinco
diafragmas en 0 kN). Un diafragma ya identifica cuerpo y nivel; el nodo
está en tal diafragma, su peso va a ese diafragma.

### Ingeniería, `Cs = 0.10`, `k = 1`

| cota | W sísmico [kN] | reparto | F [kN] |
| --- | --- | --- | --- |
| +3.96 | 16 263.83 | 10.65 % | 585.69 |
| +7.92 | 9 702.34 | 12.71 % | 698.79 |
| +11.88 | 8 869.77 | 17.43 % | 958.25 |
| +15.84 | 10 309.49 | 27.01 % | 1 485.05 |
| +19.80 | 9 827.40 | 32.19 % | 1 769.51 |
| | **V = 5 497.28** | 100 % | 5 497.28 |

### Las cuatro verificaciones

**Carga lateral total y corte basal.** La carga aplicada, 5497.283 kN,
llega al suelo con error de `1.3e-4 kN` en EX y `6.7e-5 kN` en EY. El
corte basal se le pide a `calcular.equilibrio()`, que descarta por grado
de libertad las reacciones internas del diafragma: sumar todas las filas
de reacciones daba −20 167 kN, casi cuatro veces el corte real, porque el
nodo maestro devuelve la fuerza de la restricción como si fuera un apoyo.

**Sentido de la deformada.** Tres cosas que el equilibrio no garantiza y
que se revisan piso a piso: que cada piso vaya hacia donde lo empujan,
que el desplazamiento crezca con la altura sin devolverse, y que el
movimiento fuera de la dirección de la carga no supere al de la dirección
empujada. Las tres se cumplen en EX y EY. El techo se mueve 7.46 mm bajo
EX y 23.09 mm bajo EY: el edificio es tres veces más flexible en Y, donde
tiene menos muro.

**Torsión de piso.** Se mide con el cociente de irregularidad torsional
de NCh433, `r = u_max / u_prom` sobre los nodos del diafragma en la
dirección de la carga, con el promedio de los dos extremos del piso.
`r > 1.2` es irregularidad; `r > 1.4`, extrema.

| cota | EX: u [mm] | r | EY: u [mm] | r |
| --- | --- | --- | --- | --- |
| +3.96 | 0.05 | – | 0.08 | – |
| +7.92 | 0.17 | **1.735** | 0.36 | – |
| +11.88 | 2.18 | 1.029 | 8.56 | **1.633** |
| +15.84 | 4.86 | 1.000 | 17.44 | **1.626** |
| +19.80 | 7.46 | 1.019 | 23.09 | **1.538** |

Los niveles contra el terreno casi no se mueven (0.05 mm contra 7 del
techo) y ahí el cociente no dice nada; se marca con `–`. En lo que sí se
mueve: bajo EY los tres pisos superiores tienen **torsión extrema**, con
el centro de rigidez 1.70 m fuera del geométrico. Bajo EX solo el nivel
+7.92, el primero que se despega del terreno. Es un hallazgo sobre el
edificio, no sobre el modelo: la planta es asimétrica y los muros que
resisten Y no están donde está la masa.

## 4. Parte C — Superposición

La combinación `R = 1.0 G + 0.5 Q + 1.0 EX` se obtiene de dos maneras: sumando
algebraicamente los resultados de los casos independientes, y resolviendo
en OpenSees una corrida con las cargas ya combinadas. Los tres números que
pide el enunciado:

| | superposición | corrida explícita | diferencia |
| --- | --- | --- | --- |
| desplazamiento `ux`, techo (nodo 718) | 0.00900722 m | 0.00900722 m | 0 |
| reacción `fz`, apoyo (nodo 2) | 301.8955 kN | 301.8955 kN | 5.7e-14 |
| momento `My`, viga (elem 91) | −7.26965 kN·m | −7.2696 kN·m | 5.0e-05 |

Y sobre **todo** el modelo, que es lo que prueba algo —tres números
coincidirían aunque algo estuviera mal en otro sitio—:

| familia | valores comparados | peor desacuerdo | cota de redondeo |
| --- | --- | --- | --- |
| desplazamientos | 1956 | 1.50e-08 | 1.75e-08 |
| reacciones | 438 | 1.50e-04 | 1.75e-04 |
| fuerzas internas | 6708 | 1.50e-04 | 1.75e-04 |

El criterio no es una tolerancia elegida: el motor redondea su salida a 8
decimales los desplazamientos y a 4 las fuerzas, y la cota es el error
máximo que ese redondeo puede meter al sumar los casos y compararlos
contra una corrida que también viene redondeada. El desacuerdo observado
queda **debajo** de la cota en las tres familias. La superposición no
aporta error medible.

**Por qué funciona.** El modelo es lineal elástico: `K u = F` con `K`
constante, así que `K(a·u₁ + b·u₂) = a·F₁ + b·F₂`. Las fuerzas internas y
las reacciones salen de `u` por operaciones lineales, y se combinan igual.

**Cuándo dejaría de funcionar.** En cuanto `K` deje de ser constante:
material no lineal —lo que pasa en la Parte D, donde el hormigón se
fisura y el acero fluye y por eso las curvas P-M no se superponen—,
geometría no lineal (P-Δ), contacto o despegue, o cualquier cosa que
dependa del camino de carga. En este modelo no hay nada de eso.

## 5. Parte D — Capacidad de hormigón armado

### De dónde sale la armadura

El modelo no traía enfierradura. Se revisaron las 38 láminas del proyecto
`2017_67` buscando el cuadro de pilares y **no existe**: el sistema
resistente son muros —once láminas de elevaciones de eje contra ninguna de
columnas—, y los elementos verticales se detallan como cabezales de
borde en esas elevaciones. La armadura longitudinal que aparece ahí es de
muro, `L:3+3f10` hasta `L:10+10f8`: en una sección de 0.50 × 0.50 m daría
una cuantía de 0.19 a 0.40 %, bajo el mínimo normativo. Es armadura
repartida de muro delgado, no una jaula de columna.

Lo que sí hay es el **detalle típico de pilar** de la lámina
`2017_67-000`, "Esquema estribos en vigas y pilares", cuya geometría se
midió directamente del DXF: 16 barras dibujadas como donuts en
disposición perimetral, 5 por cara, con estribo exterior cuadrado más un
segundo estribo en rombo que traba las barras de media cara (esquema
"2E"). Es la misma disposición que se dedujo para los pilares del LT2 por
otro camino —desde su estribo—, lo que da confianza en que es la práctica
del proyecto.

Trazable a plano: número de barras, disposición, topología del estribo,
espaciamiento (`φ10 a 10`, el de las elevaciones). **Supuesto: el
diámetro**, `φ16`, que es uno de los que el edificio usa. Resulta
`As = 32.17 cm²`, cuantía `1.29 %`.

La armadura se pega en la etapa de armado (`edificios/ingenieria/armar.py`
→ `enfierradura.py`), con el mismo contrato que usa el LT2, para que
`comun/capacidad.py` lea los dos edificios sin preguntar cuál es.

### La sección

```
columna (elem 18)   0.50 x 0.50 m
  hormigon   f'c = 28.0 MPa
  acero      fy  = 420 MPa, Es = 200 GPa
  refuerzo   16 barras, As = 32.17 cm2, cuantia = 1.29 %
  estribo    Ef10a10 (lamina 2017_67-000, esquema 2E)
  trabas     1 en x, 1 en y
  confinado  f'cc = 39.4 MPa (K = 1.407), eps_cc = 0.00607, eps_cu = 0.02204
```

El confinamiento **no es un número puesto a mano**: sale del estribo con
Mander. Tres materiales: núcleo confinado (`f'cc = 39.4 MPa`, hasta
`ε_cu = 0.022`, la deformación a la que se corta el estribo),
recubrimiento sin confinar (`f'c = 28 MPa`, hasta 0.004) y acero
(`Steel01`, con 1 % de endurecimiento). La sección se discretiza en 20
fibras a lo alto del núcleo —verificado que entre 20 y 40 el momento
máximo cambia menos de 0.5 %— y cada barra es una fibra propia.

`semana03/resultados/fibras_ingenieria_18.png` dibuja exactamente lo que
se le manda a OpenSees: la figura y el análisis salen de la misma función,
para que no puedan describir secciones distintas.

### M-phi

`mphi_ingenieria_18.png` muestra la curva a cuatro niveles de compresión.
El punto sobre cada curva es el hormigón a 0.003: la capacidad nominal,
la que se compara con un cálculo a mano.

| P [kN] | % de compresión pura | M nominal [kN·m] | M máximo | termina porque |
| --- | --- | --- | --- | --- |
| 0 | 0 | 256.5 | 312.4 | el núcleo llega a ε_cu |
| 1239 | 15 | 386.3 | 430.3 | el núcleo llega a ε_cu |
| 2478 | 30 | 426.6 | 456.7 | el momento cae bajo el 80 % |
| 4131 | 50 | 341.7 | 375.1 | el momento cae bajo el 80 % |

Con `P = 0` la sección es dúctil y llega a poco momento. Al subir la
compresión el momento sube, pero la curva se acaba antes: el hormigón
llega a su deformación última con menos curvatura. Más axial da más
capacidad y menos ductilidad, hasta que la compresión es tanta que la
capacidad también baja.

### Interacción P-M

La curva se construye corriendo un M-phi por cada nivel de compresión y
tomando su momento nominal, del **mismo objeto de fibras**. Integrar
aparte con una ley escrita a mano deja dos definiciones de la misma
sección que hay que mantener sincronizadas —distinta ley del hormigón,
distinta discretización— y cuando se separan nadie lo nota, porque los
dos gráficos siguen saliendo con forma razonable. Era el defecto de la
versión anterior de este script.

| P [kN] | Mn [kN·m] | de dónde |
| --- | --- | --- |
| −1351.1 | 0.0 | tracción pura: `As·fy` |
| 0.0 | 256.5 | hormigón a 0.003 |
| 826.1 | 352.3 | |
| 1652.2 | 414.0 | |
| **2478.3** | **426.6** | la nariz |
| 3304.4 | 393.6 | |
| 4130.5 | 341.7 | |
| 5369.7 | 204.6 | |
| 8261.1 | 0.0 | compresión pura: `f'c(Ag−As) + fy·As` |

**Interpretación.** Tracción pura: solo el acero, `32.17 cm² × 420 MPa
= 1351 kN`; el hormigón no toma tracción. Compresión pura: sin
excentricidad no hay momento; 8261 kN es el tope teórico. Entre medio el
momento primero **sube** con P —la compresión cierra las fisuras y
retrasa la fluencia del acero traccionado— hasta la nariz en 2478 kN,
donde admite 427 kN·m, 1.7 veces lo que admite sin axial; y después
**baja**: con más compresión el hormigón se aplasta antes de que el acero
llegue a fluir. Por eso la sección no tiene "un" momento resistente: tiene
uno por cada nivel de carga axial, y la demanda hay que compararla contra
el que corresponde a **su** compresión.

### Demanda contra capacidad

`demanda_capacidad.py` toma el `(P, M)` de la columna 18 de los casos ya
resueltos —el momento resultante `√(My² + Mz²)`, porque una columna
cuadrada con armadura perimetral resiste parecido en cualquier
dirección— y lo pone sobre su curva (`pm_ingenieria_18.png`):

| caso | P [kN] | M [kN·m] | Mn a ese P | utilización |
| --- | --- | --- | --- | --- |
| G | 3385.9 | 34.6 | 388.5 | 0.089 |
| Q | 684.5 | 7.1 | 336.4 | 0.021 |
| EX | 4.8 | 16.2 | 257.1 | 0.063 |
| EY | 50.9 | 33.8 | 262.6 | 0.129 |

Es la columna más cargada del edificio bajo G, y usa el 9 % de su
capacidad a momento. La comparación completa exige combinaciones
normativas y factores de reducción; esto es la demostración de que
demanda y capacidad se pueden poner en el mismo gráfico.

### La Fiber Section contra el cálculo a mano

`verificar_rc.py` calcula los puntos característicos con el bloque de
Whitney y compatibilidad de deformaciones, y los compara. No se espera
que den lo mismo; se espera que las diferencias se **expliquen**:

| punto | a mano | fibras | diferencia | por qué |
| --- | --- | --- | --- | --- |
| tracción pura | −1351.1 kN | −1351.1 kN | 0 | es `As·fy`: tiene que coincidir |
| flexión pura | 273.4 kN·m | 256.5 kN·m | 6.6 % | Whitney vs parábola, y el endurecimiento: la barra más traccionada llega a ε = 0.0126, donde `Steel01` da 441 MPa |
| balanceado | 529.2 kN·m | 424.6 kN·m | 24.6 % | la mitad es el confinamiento (sin confinar da 442); el resto es Whitney con axial alto, donde no fue calibrado |
| compresión pura | 7224.6 kN | 8261.1 kN | 12.5 % | exactamente el 0.85 de ACI sobre el hormigón |

## 6. Hallazgos

1. **Torsión extrema** en el edificio de Ingeniería bajo EY en los tres
   pisos superiores (`r` de 1.54 a 1.63) y bajo EX en el nivel +7.92
   (1.735). En el LT2, `r ≈ 1.70` en los cinco pisos bajo EY, con el
   centro de rigidez 11 m fuera del geométrico: los muros que resisten Y
   están todos en la caja de ascensores.
2. **El LT2 trae dos intensidades de carga viva**, 500 y 300 kgf/m², y el
   enunciado pide una. Escalar el caso Q por un factor único no la da;
   reconstruirlo por elemento sí.
3. **El conjunto repartía el peso sísmico a un solo cuerpo.** Dos
   diafragmas por nivel a la misma cota, y el reparto por cota más
   cercana dejaba cinco en cero. Corregido repartiendo por pertenencia al
   diafragma.
4. **No hay cuadro de pilares** en el proyecto `2017_67`: las columnas del
   modelo son una idealización de 0.50 × 0.50 fijada en `benchmark_3d.py`;
   los verticales reales son cabezales de muro. La armadura adoptada es el
   detalle típico de la lámina `-000`, con el diámetro como único dato
   supuesto.

## 7. Qué cambió respecto de la versión anterior

- `capacidad_ha.py` se borró. Corría el M-phi con `P = 0` —una viga, no
  una columna—, integraba la P-M con una ley de hormigón distinta a la de
  la sección de OpenSees, barría el eje neutro hasta 3 m en una sección
  de 0.50 y un casco convexo descartaba dos tercios de los puntos. Todo
  eso lo hace ahora `comun/capacidad.py`, con una sola definición de la
  sección y confinamiento de Mander.
- El laboratorio recibe el edificio por argumento y los parámetros por
  línea de comandos, y se los pide a `comun/sismo.py` y `comun/combinar.py`
  en vez de reimplementar las verificaciones.
- La enfierradura del edificio de Ingeniería se pega al armar el modelo,
  no parcheando el JSON después.

## 8. Limitaciones

- `Cs` es un coeficiente de trabajo, no un análisis de NCh433.
- La sección de 0.50 × 0.50 m es la del modelo, no la de un pilar del
  plano, que no existe como tal.
- El diámetro `φ16` es supuesto; el resto de la armadura viene de la
  lámina `-000`.
- La comparación demanda-capacidad es nominal, sin combinaciones
  mayoradas ni factores de reducción.
- El modelo es lineal elástico; la capacidad no lineal es de la sección
  aislada, no del edificio.
