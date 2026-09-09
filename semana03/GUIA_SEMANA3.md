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

La primera verificación consiste en comprobar que la suma de las áreas
tributarias representa el área total de losa:

```text
sum(A_i) = A_losa
```

La segunda verificación comprueba que la suma de cargas transferidas es la
carga superficial total:

```text
sum(Q_i) = q_Q * A_losa
```

Luego se comparan esas cargas con las reacciones verticales calculadas por
OpenSees:

```text
sum(Rz) aproximadamente igual a Q_total
```

Las dos verificaciones tienen significados distintos:

* La primera comprueba la transferencia de carga desde la losa hacia las
  vigas.
* La segunda comprueba el equilibrio global del modelo en OpenSees.

Si se conserva el área pero la asignación entre vigas es incorrecta, la suma
global podría cerrar igualmente. Por eso también es importante revisar las
áreas individuales y, cuando sea posible, su distribución por nivel.

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

La fuerza de cada nivel se obtiene distribuyendo el corte basal según el peso
del nivel y su altura respecto de la base:

```text
F_i = V * (W_i*h_i) / sum(W_j*h_j)
```

Donde:

* `F_i` es la fuerza sísmica aplicada en el nivel `i`.
* `V` es el corte basal total.
* `W_i` es el peso sísmico del nivel `i`.
* `h_i` es la altura del nivel `i` medida desde la base.
* `sum(W_j*h_j)` normaliza el reparto entre todos los niveles.

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

Además del equilibrio, se deben observar:

* desplazamientos horizontales;
* dirección de la deformación;
* diferencias entre la respuesta en X y en Y;
* posible rotación o torsión del diafragma.

Por ejemplo, en el resultado del modelo el caso `EX` debe producir
principalmente desplazamiento `ux`, mientras que `EY` debe producir
principalmente desplazamiento `uy`. Un valor de `rz` permite observar si
existe rotación del diafragma.

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

En esta entrega, la sección de columna es de `0.50 x 0.50 m`. Como el
repositorio no contiene armadura real de hormigón armado extraída de planos,
la armadura utilizada se identifica explícitamente como supuesto académico de
laboratorio.

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
resistir antes de alcanzar un estado límite.

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
