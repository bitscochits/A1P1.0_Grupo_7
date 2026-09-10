# Semana 3 — Guía de estudio y defensa

## 1. ¿Qué busca el profesor en esta semana?

En las semanas anteriores se construyó y validó el modelo estructural en
OpenSees. Ese trabajo dejó disponible la geometría, los materiales, las
cargas, los apoyos, los diafragmas y los resultados de distintos casos.

En Semana 3 no se reconstruye el edificio. Se utiliza el modelo existente para
responder cuatro preguntas:

| Parte               | Pregunta que debemos responder                                                                                     |
| ------------------- | ------------------------------------------------------------------------------------------------------------------ |
| A — Carga viva      | ¿La carga viva de la losa se transfirió correctamente a las vigas?                                                 |
| B — Sismo EX/EY     | ¿El modelo responde correctamente ante fuerzas sísmicas en X e Y?                                                  |
| C — Superposición   | ¿Podemos combinar resultados de casos independientes y obtener el mismo resultado que aplicando las cargas juntas? |
| D — Hormigón armado | ¿Qué capacidad tiene una sección de columna de hormigón armado?                                                    |

La estructura conceptual de la entrega es:

```text
MODELO DEL EDIFICIO
→ G, Q, EX, EY
→ DEMANDA
→ desplazamientos, reacciones y fuerzas internas
```

Y, por otro lado:

```text
SECCIÓN DE COLUMNA
→ Fiber Section
→ M-phi y P-M
→ CAPACIDAD
```

La idea final es:

```text
Demanda <= Capacidad
```

Esto significa que las solicitaciones producidas por las cargas deben poder
ser resistidas por la capacidad de los elementos estructurales.

## 2. Parte A — Carga viva Q

La losa tiene una carga viva superficial denominada:

```text
q_Q [kN/m2]
```

Cada viga recibe una parte de esa carga según su área tributaria `A_i`. El
área tributaria es la superficie de losa cuya carga se asigna a una viga
determinada.

La carga viva transferida a cada viga es:

```text
Q_i = q_Q * A_i
```

### Ejemplo

Si:

```text
q_Q = 2 kN/m2
A_i = 10 m2
```

entonces:

```text
Q_i = 2 kN/m2 * 10 m2
Q_i = 20 kN
```

El caso Q se construye poniendo `q_Q * A_i` en cada elemento que recibe
losa, por la misma vía que en el modelo: repartida sobre la viga, o
puntual en la cabeza del muro. Con eso, la conservación

```text
sum(Q_i) = q_Q * A_losa
```

es una **identidad**: así se construyó, y da igual esté el modelo bien o
mal. Conviene decirlo así en la defensa, porque es la pregunta obvia.

Lo que sí verifica algo es que la carga llegue **entera al suelo**:

```text
sum(Rz) aproximadamente igual a q_Q * A_losa
```

Si el modelo pierde carga por un elemento suelto o una carga huérfana, las
reacciones no cierran. En los tres edificios cierran a `1e-8` relativo.

Y que la construcción **cubra toda la losa**: cada carga nodal del modelo
tiene que corresponder a un elemento con área, y cada elemento con área
tiene que bajar por algún lado. Si no, el script se detiene con el
elemento que sobra, en vez de adivinar.

Por qué no basta con escalar el caso Q del modelo por un factor: el plano
del LT2 trae dos intensidades, 500 kgf/m² en los pisos y 300 en el techo.
Un factor único deja el techo a una presión y los pisos a otra, ninguna
igual a `q_Q`. El enunciado pide **una** intensidad.

La revisión fina del reparto —que cada viga reciba lo que dibuja su
polígono, piso por piso— es `comun/verificar_tributarias.py`.

## 3. Parte B — Sismo pseudoestático EX y EY

La base física del cálculo pseudoestático es la segunda ley de Newton:

```text
F = m*a
```

El peso y la masa se relacionan mediante:

```text
W = m*g
```

por lo tanto:

```text
m = W/g
```

Si la aceleración sísmica equivalente se expresa como:

```text
a = Cs*g
```

entonces:

```text
F = (W/g) * (Cs*g)
F = Cs*W
```

Para el modelo se utiliza el peso sísmico por nivel:

```text
W_sismico = G + 0.5Q
```

Esto **NO** significa que el sismo sea una combinación de cargas `G + 0.5Q`.
Significa que ese peso se utiliza para estimar la masa sísmica que participa
en el cálculo de las fuerzas laterales.

El corte basal total es:

```text
V = Cs * W_sismico
```

El corte basal es la resultante horizontal de todas las fuerzas sísmicas
aplicadas sobre el edificio. Es decir, es la fuerza sísmica total que debe
ser equilibrada por las reacciones de la base.

La fuerza de cada nivel es una fracción del corte basal. **Cómo se reparte
lo define el profesor**, y por eso es un parámetro y no está fijo en el
código:

```text
F_i = V * (W_i * h_i^k) / sum(W_j * h_j^k)
```

* `k = 0`: uniforme, proporcional solo a la masa.
* `k = 1`: triangular invertido, el clásico. Es el valor por defecto.
* `k = 2`: el límite superior de NCh433 / ASCE 7.
* o un reparto **manual**, dictado nivel por nivel de abajo hacia arriba,
  que se normaliza solo.

Donde `W_i` es el peso sísmico del nivel `i` y `h_i` su altura desde la
base. Para el edificio de Ingeniería con `k = 1` el techo toma el 32 % del
corte y el primer nivel el 11 %; con `k = 2`, el 45 % y el 3 %.

El peso `W_i` se reparte **por diafragma, no por cota**. En el conjunto hay
dos diafragmas por nivel —uno por cuerpo— a la misma altura; buscar por
cota dejaba al segundo cuerpo sin sismo.

En este proyecto existen dos casos independientes:

```text
EX = sismo en dirección X
EY = sismo en dirección Y
```

Se estudian por separado porque el edificio puede tener diferente rigidez,
geometría, distribución de muros y respuesta torsional en ambas direcciones.

Las verificaciones principales son:

```text
sum(Fx_i) = Vx
```

y:

```text
sum(Fy_i) = Vy
```

También se verifica el equilibrio de las reacciones:

```text
sum(Rx) aproximadamente igual a -Vx
sum(Ry) aproximadamente igual a -Vy
```

El signo negativo aparece porque las reacciones se oponen a las fuerzas
aplicadas.

Ojo con el corte basal: sumar **todas** las filas de reacciones lo da al
cuádruple. El nodo maestro de un diafragma devuelve la fuerza de la
restricción como si fuera un apoyo, y esa fuerza es interna. Hay que
descartarla por grado de libertad, que es lo que hace
`calcular.equilibrio()`.

Además del equilibrio, el enunciado pide el **sentido de la deformada** y
la **torsión de piso**. Las revisa `comun/sismo.py`:

*Sentido de la deformada* son tres cosas que un equilibrio correcto no
garantiza:

1. cada piso se mueve **hacia donde** lo empujan, con el mismo signo que la
   fuerza;
2. el desplazamiento **crece con la altura** sin devolverse; un piso que se
   mueve menos que el de abajo delata un piso blando mal modelado o una
   barra suelta;
3. el movimiento **no se sale de su dirección**: bajo `EX` el edificio se
   mueve sobre todo en X. Algo de Y siempre hay, porque la planta no es
   simétrica; pero si `uy` supera a `ux`, los ejes están cruzados.

*Torsión de piso.* Un diafragma rígido se traslada y además **gira**, cuando
el centro de rigidez no coincide con el punto por donde entra la fuerza.
La medida de NCh433 es el cociente de irregularidad torsional:

```text
r = u_max / u_prom       sobre los nodos del piso, en la dirección de la carga
```

con `u_prom` la media de los dos extremos del piso. `r = 1` es traslación
pura; `r > 1.2` es irregularidad torsional; `r > 1.4`, extrema. Se mide en
los nodos del diafragma, no en el maestro: el maestro está en el centro de
masa y por definición no ve el giro.

En el edificio de Ingeniería el techo se mueve 7.5 mm bajo `EX` y 23.1 mm
bajo `EY`: es tres veces más flexible en Y. Y bajo `EY` los tres pisos
superiores tienen **torsión extrema**, `r` entre 1.54 y 1.63, con el centro
de rigidez 1.7 m fuera del geométrico. Es un hallazgo sobre el edificio: la
planta es asimétrica y los muros que resisten Y no están donde está la masa.

## 4. Parte C — Superposición

Los casos independientes son:

```text
G
Q
EX
EY
```

Una combinación general puede escribirse como:

```text
R =
lambda_G*G +
lambda_Q*Q +
lambda_EX*EX +
lambda_EY*EY
```

Por ejemplo, una combinación para la demostración puede ser:

```text
1.0G + 0.5Q + 1.0EX
```

La justificación matemática parte del equilibrio lineal:

```text
K*u = F
```

Despejando el vector de desplazamientos:

```text
u = K^-1 F
```

Si la carga total está formada por dos cargas:

```text
F = F1 + F2
```

entonces:

```text
u = K^-1(F1 + F2)
```

Por linealidad del operador `K^-1`:

```text
u = K^-1F1 + K^-1F2
```

Por lo tanto:

```text
u = u1 + u2
```

La entrega debe demostrar la superposición por dos caminos:

1. Superposición algebraica de resultados independientes.
2. Corrida explícita aplicando las cargas simultáneamente en OpenSees.

Los dos métodos deben producir resultados aproximadamente iguales. Se debe
comparar al menos:

* un desplazamiento;
* una reacción;
* una fuerza interna.

Conceptualmente, se espera:

```text
R_superposicion aproximadamente igual a R_corrida_explicita
```

En la implementación se deben comparar los valores, el error absoluto y el
error relativo.

La superposición deja de ser válida, o deja de ser directamente aplicable,
cuando la rigidez depende del estado de la estructura. Ejemplos:

* materiales no lineales;
* plastificación;
* daño;
* contacto;
* grandes deformaciones;
* rigidez dependiente del estado de la estructura.

En esos casos, resolver cada carga por separado y sumar resultados no equivale
necesariamente a aplicar todas las cargas juntas.

## 5. Parte D — Capacidad de hormigón armado

Las Partes A, B y C estudian principalmente la **DEMANDA**: las cargas que
actúan sobre el modelo y la respuesta que producen.

La Parte D comienza a estudiar la **CAPACIDAD**: cuánto puede resistir una
sección estructural antes de alcanzar estados límite relevantes.

Se toma una sección representativa de columna de hormigón armado. La sección
se estudia como un elemento aislado, sin modificar el comportamiento del
modelo global del edificio.

## 6. Fiber Section

Una `Fiber Section` divide una sección transversal en muchas pequeñas regiones
llamadas fibras.

Cada fibra debe tener:

* área `A_i`;
* posición `y_i`;
* material;
* deformación `epsilon_i`;
* tensión `sigma_i`.

La compatibilidad de deformaciones se expresa como:

```text
epsilon(y) = epsilon_0 - phi*y
```

Donde:

* `epsilon_0` es la deformación axial de referencia;
* `phi` es la curvatura de la sección;
* `y` es la posición de la fibra respecto del eje de referencia.

Cada fibra obtiene su deformación y luego su tensión mediante la ley
constitutiva de su material:

```text
sigma_i = f(epsilon_i)
```

Finalmente se integran las tensiones sobre toda la sección:

```text
P = sum(sigma_i*A_i)
```

y:

```text
M = sum(sigma_i*A_i*y_i)
```

Una fibra representa una pequeña porción de hormigón o acero con una ley
constitutiva propia. Las fibras de hormigón y las fibras de acero no tienen
por qué comportarse igual: cada material tiene una relación tensión-
deformación diferente.

En esta entrega, la sección de columna es de `0.50 x 0.50 m`, la de las 82
columnas del modelo. La armadura:

* **Se revisaron las 38 láminas del proyecto y no hay cuadro de pilares.**
  El sistema resistente son muros; los verticales reales se detallan como
  cabezales de borde en las once elevaciones de eje. La armadura que
  aparece ahí es de muro (`L:3+3f10` a `L:10+10f8`), que en 0.50 × 0.50
  daría una cuantía de 0.19 a 0.40 %, bajo el mínimo normativo.
* Se adopta el **detalle típico de pilar de la lámina `2017_67-000`**,
  medido del DXF: 16 barras perimetrales, 5 por cara, estribo exterior más
  rombo (esquema "2E"). Es la misma disposición que se dedujo para el LT2
  desde su estribo, por otro camino.
* **Trazable a plano**: número de barras, disposición, estribos, `φ10 a 10`.
  **Supuesto**: el diámetro, `φ16`, que es uno de los que el edificio usa.
  Da `As = 32.17 cm²` y cuantía `1.29 %`.

El confinamiento del núcleo **no es un número puesto a mano**: sale del
estribo con Mander, `f'cc = 39.4 MPa`, y el núcleo llega a `ε_cu = 0.022`,
la deformación a la que se corta el estribo. Tres materiales: núcleo
confinado, recubrimiento sin confinar y acero.

## 7. Curva momento-curvatura M-phi

En la curva momento-curvatura:

```text
M = momento
phi = curvatura
```

La curva `M-phi` muestra cómo evoluciona la respuesta resistente de la
sección cuando aumenta su curvatura.

En la curva se deben identificar, cuando el análisis los alcanza:

* la rigidez inicial aproximadamente lineal;
* el cambio de rigidez;
* el comportamiento no lineal;
* la fluencia del acero si aparece;
* la capacidad máxima aproximada;
* el comportamiento posterior a la capacidad máxima, si está representado.

La pendiente inicial de la curva representa una rigidez flexional
aproximada. Cuando el acero o el hormigón cambian de régimen, la pendiente
puede disminuir y la respuesta deja de ser lineal.

La curva se corre a **varios niveles de compresión**, porque una columna
sin axial es una viga. Para la columna 18:

| P [kN] | M nominal [kN·m] | termina porque |
| --- | --- | --- |
| 0 | 256 | el núcleo llega a `ε_cu` |
| 1239 | 386 | el núcleo llega a `ε_cu` |
| 2478 | 427 | el momento cae bajo el 80 % del máximo |
| 4131 | 342 | el momento cae bajo el 80 % del máximo |

Con `P = 0` la sección es dúctil y llega a poco momento. Al subir la
compresión el momento sube, pero la curva se acaba antes. Más axial da
más capacidad y menos ductilidad, hasta que la compresión es tanta que la
capacidad también baja. Eso es la respuesta a "¿por qué P cambia M?", con
un gráfico.

El "M nominal" es el momento cuando la fibra de hormigón más comprimida
llega a 0.003: la convención de ACI, la que se compara con un cálculo a
mano. Es siempre menor que el máximo de la curva, porque después de ese
punto el núcleo confinado sigue tomando carga y el acero endurece.

## 8. Interacción P-M

En una columna:

```text
P = carga axial
M = momento
```

Una columna normalmente trabaja con ambos efectos simultáneamente. La curva
de interacción `P-M` muestra combinaciones resistentes de carga axial y
momento.

La capacidad a flexión no es necesariamente la misma para todos los valores
de carga axial. La fuerza `P` modifica el estado de deformaciones y tensiones
de las fibras, por lo que también modifica la capacidad de momento `M`.

Algunos puntos de la curva representan aproximadamente:

* carga axial cercana a cero y momento importante;
* momento cercano a cero y carga axial importante;
* estados intermedios de carga axial y flexión.

La curva permite observar que la sección no tiene una única capacidad de
momento independiente de la carga axial.

**Cómo se construye.** Corriendo un M-phi por cada nivel de compresión y
tomando su momento nominal, del **mismo objeto de fibras**. Integrar la
P-M aparte, con una ley escrita a mano, deja dos definiciones de la misma
sección que hay que mantener sincronizadas; cuando se separan nadie lo
nota, porque los dos gráficos siguen saliendo con forma razonable. Era el
defecto de la versión anterior del script.

**La forma, con los números de la columna 18.** Tracción pura en
`P = −1351 kN`: es `As · fy`, solo el acero. Compresión pura en `8261 kN`:
sin excentricidad no hay momento. Entre medio el momento **sube** con P
—la compresión cierra las fisuras y retrasa la fluencia del acero
traccionado— hasta la nariz en `P = 2478 kN`, `M = 427 kN·m`, 1.7 veces lo
que admite sin axial; y después **baja**: el hormigón se aplasta antes de
que el acero fluya.

**Demanda sobre la curva.** La columna 18, la más cargada bajo G, tiene
`P = 3386 kN` y `M = 35 kN·m`. A ese axial la curva admite 388 kN·m: usa
el 9 %. La comparación completa exige combinaciones mayoradas y factores
de reducción; esto es la demostración de que demanda y capacidad se
pueden poner en el mismo gráfico.

## 9. Demanda versus capacidad

La separación conceptual de la entrega es:

```text
MODELO GLOBAL
→ G, Q, EX, EY
→ desplazamientos, reacciones y esfuerzos
→ DEMANDA
```

frente a:

```text
SECCIÓN DE HORMIGÓN ARMADO
→ Fiber Section
→ M-phi y P-M
→ CAPACIDAD
```

La idea final es:

```text
Demanda <= Capacidad
```

La comparación completa entre demanda y capacidad requiere definir criterios
de diseño, combinaciones normativas, factores de seguridad y propiedades
reales de materiales y armaduras. La Parte D de esta semana constituye una
demostración de capacidad de sección, no un diseño normativo completo del
edificio.

## 10. ¿Qué ya existía antes de Semana 3?

El proyecto ya contiene:

* geometría;
* nodos;
* vigas;
* columnas;
* muros;
* apoyos;
* propiedades estructurales;
* áreas tributarias;
* carga permanente;
* carga viva;
* casos `G`, `Q`, `EX` y `EY`;
* resultados de OpenSees;
* conexión con Unity.

Semana 3 no reconstruye todo el edificio. Utiliza esos datos para realizar
verificaciones específicas:

* leer las áreas tributarias existentes;
* leer la carga viva existente;
* leer los resultados guardados;
* reutilizar el motor común de OpenSees;
* ejecutar comprobaciones de equilibrio y superposición.

## 11. ¿Qué agrega Semana 3?

### Parte A

Se verifica la conservación de la carga viva:

```text
sum(Q_transferida) = q_Q*A
```

### Parte B

Se verifica el corte basal sísmico:

```text
V = Cs*W_sismico
```

También se verifica la distribución por nivel:

```text
sum(F_i) = V
```

Además se revisa el equilibrio de reacciones y la dirección de los
desplazamientos.

### Parte C

Se verifica que:

```text
R_superposicion aproximadamente igual a R_corrida_explicita
```

comparando desplazamientos, reacciones y fuerzas internas.

### Parte D

Se agregan:

```text
M-phi
```

y:

```text
P-M
```

para estudiar la capacidad aproximada de una sección de hormigón armado.

## 12. Preguntas de defensa

### 1. ¿Qué es un área tributaria?

Es la superficie de losa cuya carga se asigna a una viga determinada. La suma
de las áreas tributarias debe representar el área de losa que se está
transfiriendo.

### 2. ¿Por qué debe conservarse la carga viva?

Porque la carga no puede desaparecer ni crearse durante la transferencia. La
suma de las cargas recibidas por las vigas debe ser igual a la carga viva
superficial total de la losa.

### 3. ¿Qué representa EX?

Representa el caso de carga sísmica pseudoestática aplicado en la dirección
X. Las fuerzas laterales se aplican en los nodos maestros de los diafragmas.

### 4. ¿Qué representa EY?

Representa el caso de carga sísmica pseudoestática aplicado en la dirección
Y. Es independiente de `EX` y permite estudiar la respuesta en la otra
dirección principal.

### 5. ¿De dónde sale F = Cs*W?

De `F = m*a`, usando `W = m*g` y `a = Cs*g`. Al reemplazar `m = W/g`, queda
`F = (W/g)*(Cs*g) = Cs*W`.

### 6. ¿Qué significa W_sismico = G + 0.5Q?

Significa que se estima la masa sísmica usando todo el peso permanente y la
mitad de la carga viva. No significa que el caso sísmico sea una combinación
de cargas verticales `G + 0.5Q` aplicada como tal.

### 7. ¿Qué es el corte basal?

Es la fuerza horizontal resultante de todas las fuerzas sísmicas aplicadas en
los niveles del edificio. Debe ser equilibrada por las reacciones de la base.

### 8. ¿Por qué se distribuye por altura?

Porque los niveles superiores tienen mayor brazo respecto de la base y, según
la regla utilizada, reciben una proporción de fuerza asociada a `W_i*h_i`.

### 9. ¿Por qué funciona la superposición?

Porque el modelo utilizado es lineal elastico y cumple `K*u = F`. La respuesta
para una suma de cargas es la suma de las respuestas individuales.

### 10. ¿Cuándo deja de funcionar?

Cuando la rigidez cambia con el estado de la estructura, por ejemplo por
plastificación, daño, contacto o grandes deformaciones.

### 11. ¿Qué es una Fiber Section?

Es una representación de la sección transversal dividida en muchas fibras,
cada una con su posición, área y material.

### 12. ¿Qué representa una fibra?

Representa una pequeña porción de hormigón o acero. Su deformación depende de
su posición y su tensión se calcula con la ley constitutiva del material.

### 13. ¿Qué es la curva momento-curvatura?

Es la relación entre el momento resistente `M` y la curvatura `phi` de una
sección. Permite observar rigidez, cambios de régimen y capacidad flexional.

### 14. ¿Qué representa la interacción P-M?

Representa combinaciones de carga axial `P` y momento `M` que la sección puede
resistir bajo una hipótesis de compatibilidad de deformaciones.

### 15. ¿Por qué P modifica M?

Porque la carga axial cambia las deformaciones y tensiones de las fibras. Al
cambiar el estado axial, cambia también la distribución de tensiones que
produce el momento resistente.

### 16. ¿Qué diferencia existe entre demanda y capacidad?

La demanda es lo que las cargas producen en la estructura: desplazamientos,
reacciones y esfuerzos. La capacidad es lo que un elemento o sección puede
resistir antes de alcanzar un estado límite. La demanda se combina
(el modelo es lineal); la capacidad no (la sección no lo es), y por eso se
calcula entera para cada nivel de axial.

### 17. ¿De dónde sale la armadura de la columna?

Del detalle típico de pilar de la lámina `2017_67-000`, medido del DXF: 16
barras perimetrales, 5 por cara, estribo exterior más rombo. El proyecto
**no tiene cuadro de pilares** —se revisaron las 38 láminas— porque su
sistema resistente son muros. Lo único supuesto es el diámetro, `φ16`, que
es uno de los que el edificio usa.

### 18. ¿Qué verifica de verdad la Parte A, si `sum(Q) = q·A` es identidad?

Que la carga llegue entera al suelo: las reacciones de OpenSees contra lo
aplicado, a `1e-8`. Y que la construcción cubra toda la losa sin cargas
huérfanas ni elementos que no bajen por ningún lado.

### 19. ¿Qué es el cociente de torsión y qué dice de este edificio?

`u_max / u_prom` sobre los nodos del piso, en la dirección de la carga.
Con `r = 1` el piso solo se traslada; `r > 1.4` es torsión extrema para
NCh433. Este edificio da 1.54 a 1.63 en los tres pisos superiores bajo EY:
la planta es asimétrica y los muros que resisten Y no están donde está la
masa.

### 20. ¿Por qué el corte basal no es la suma de todas las reacciones?

Porque el nodo maestro del diafragma devuelve la fuerza de la restricción
como si fuera un apoyo, y esa fuerza es interna. Sumando todo sale −20 167
kN contra 5497 aplicados. Hay que descartarla por grado de libertad.

### 21. En el visor hay vigas que se hunden mucho en el medio. ¿Están cortadas?

Están partidas en dos elementos, sí, pero **eso no es lo que las hunde y no
las corta estructuralmente**. Partir una viga en dos elementos que comparten
un nodo no le pone una rótula: los seis grados de libertad son los mismos,
el momento pasa entero. Es la forma de conectarle la viga perpendicular; sin
ese nodo, la otra viga no tendría dónde apoyarse.

La prueba es refinar la malla. Si el corte fuera el problema, poner más
tramos cambiaría la respuesta:

| malla | uz nodo 373 | flecha relativa |
| --- | --- | --- |
| 2 tramos (como está) | −8.8524 mm | −6.5500 mm |
| 4 tramos | −8.8524 mm | −6.5500 mm |
| 8 tramos | −8.8524 mm | −6.5500 mm |
| 16 tramos | −8.8524 mm | −6.5500 mm |

Idéntico al cuarto decimal. El elemento es correcto.

**Lo que sí la hunde** es que en ese punto aterriza una viga secundaria de
7.5 m que trae 25 m² de losa, y ahí no hay columna. Quitándole esa losa la
flecha relativa cae de 6.55 mm a 0.96 mm: **el 85 % lo trae la viga
perpendicular**.

**Y la flecha es chica.** 6.55 mm sobre un vano de 10 m es `L/1527`, muy
lejos del `L/360` de la norma. Lo que se ve grande es la **escala gráfica
×300** del visor: 6.55 mm dibujados ×300 son casi 2 m de hundimiento sobre
una viga de 10 m. Bajando la escala con el slider del panel, la viga vuelve
a verse recta. La escala es solo visual y no toca el cálculo.

Dato curioso que salió al probarlo: poner una columna bajo ese nodo **no
mejora nada** —la flecha pasa de 6.55 a 7.08 mm— porque el piso de abajo, en
ese mismo punto, tampoco tiene apoyo. La columna solo traslada la carga a
otro punto que también cuelga.

### 22. ¿Cómo se cambian los parámetros en vivo?

Por línea de comandos, sin editar nada: `--q 2.5 --cs 0.20 --k 2`, o
`--patron manual --fracciones 5 10 20 30 35`, o `--comb 1.2 1.0 1.4 0`.
Los valores por defecto y su justificación están en `parametros.json`.

## 13. Resumen final

| Parte | Qué hacemos               | Qué demostramos                |
| ----- | ------------------------- | ------------------------------ |
| A     | Repartimos la carga viva  | Conservación de carga          |
| B     | Aplicamos sismo en X e Y  | Equilibrio y respuesta lateral |
| C     | Combinamos casos de carga | Superposición lineal           |
| D     | Analizamos una sección HA | Capacidad M-phi y P-M          |

Semana 1-2:

```text
construcción y validación del modelo
```

Semana 3:

```text
uso del modelo para realizar verificaciones
```

La idea que todos los integrantes deberían poder explicar es:

> En Semana 3 utilizamos el modelo estructural ya desarrollado para verificar
> la transferencia de cargas, estudiar la respuesta sísmica, demostrar la
> superposición en el régimen lineal y comenzar a estudiar la capacidad no
> lineal de una sección de hormigón armado.

## Parámetros que puede entregar el profesor

Los valores por defecto y su justificación están en
`semana03/parametros.json`. Durante la actividad **no se edita nada**: se
pasan por línea de comandos.

```text
Profesor dicta parámetros
        ↓
python semana03/lab_semana03.py ingenieria --cs 0.20 --k 2
        ↓
revisar verificaciones
```

| Bandera | Significado |
| --- | --- |
| `--q` | intensidad de carga viva, kN/m² |
| `--cs` | coeficiente sísmico, fracción de g |
| `--fq` | fracción de Q que entra al peso sísmico |
| `--patron` | `potencia` o `manual` |
| `--k` | exponente del patrón `potencia`: 0 uniforme, 1 triangular, 2 NCh433 |
| `--fracciones` | reparto manual, de abajo hacia arriba; se normaliza solo |
| `--comb` | los cuatro factores de la combinación: G Q EX EY |
| `--combinacion` | una de las declaradas en el JSON |

Un valor sin sentido físico detiene el script con el mensaje de qué está
mal. Nada de esto toca el modelo ni sus resultados guardados: cambia lo
que se le pide al modelo.
