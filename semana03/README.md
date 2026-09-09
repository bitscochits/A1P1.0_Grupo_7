# Semana 3 — Entrega final

Esta carpeta contiene la demostracion de Semana 3 del curso de Metodos
Computacionales en Obras Civiles.

La entrega reutiliza el modelo estructural existente del Edificio de
Ingenieria. No reconstruye el edificio ni modifica su benchmark. Lee
`data/modelo/ingenieria.json`, construye una copia del modelo en memoria y
utiliza el motor comun de OpenSees para realizar las verificaciones.

La semana se divide en dos ideas:

```text
MODELO GLOBAL DEL EDIFICIO
G, Q, EX, EY
        ↓
DEMANDA: desplazamientos, reacciones y fuerzas internas
```

y:

```text
SECCION AISLADA DE COLUMNA
Fiber Section
        ↓
CAPACIDAD: M-phi e interaccion P-M
```

La idea final es:

```text
Demanda <= Capacidad
```

La comparacion completa requeriria criterios normativos, factores de
seguridad, combinaciones de diseno y armaduras reales. Esta entrega es una
demostracion computacional de demanda, equilibrio, superposicion y capacidad
de seccion.

## 1. Estructura de archivos

Los archivos propios de Semana 3 son:

| Archivo | Funcion |
| --- | --- |
| `semana03/parametros.py` | Valores que puede cambiar el profesor durante la actividad. |
| `semana03/lab_semana03.py` | Partes A, B y C: Q, sismo y superposicion. |
| `semana03/capacidad_ha.py` | Parte D: Fiber Section, M-phi y P-M. |
| `semana03/resultados/discretizacion_seccion.png` | Discretizacion en fibras, confinamiento y barras. |
| `semana03/resultados/momento_curvatura.png` | Grafico M-phi, para tres niveles de axial. |
| `semana03/resultados/interaccion_PM.png` | Grafico de interaccion P-M con la demanda del modelo. |

El archivo `semana03/GUIA_SEMANA3.md` contiene una guia extensa de estudio y
defensa oral.

Los archivos que se reutilizan son:

| Archivo | Informacion reutilizada |
| --- | --- |
| `data/modelo/ingenieria.json` | Nodos, elementos, secciones, apoyos, diafragmas y casos de carga base. |
| `edificios/ingenieria/benchmark_3d.py` | Modelo base original del edificio. |
| `comun/servidor_opensees.py` | Constructor y solver comun de OpenSees. |

## 2. Preparar el entorno

Abrir PowerShell y entrar al repositorio personal:

```powershell
cd C:\Users\mcubi\A1P1.0_Grupo_7_semana3
```

Comprobar la ubicacion y los archivos principales:

```powershell
Get-Location
Test-Path .\data\modelo\ingenieria.json
Test-Path .\semana03\parametros.py
Test-Path .\semana03\lab_semana03.py
```

Los tres comandos `Test-Path` deben responder `True`.

Si las dependencias no estan instaladas, preparar un entorno virtual:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

En una terminal nueva se debe activar nuevamente:

```powershell
.\.venv\Scripts\Activate.ps1
```

Las dependencias principales son `openseespy`, `matplotlib`, `numpy` y
`flask`. Flask se importa porque el motor comun comparte codigo con el
servidor de reanalisis, aunque el script no levanta un servidor HTTP.

## 3. Parametros centralizados

Los valores variables de la actividad estan en un unico archivo:

```text
semana03/parametros.py
```

Su contenido base es:

```python
q_Q = 2.0
coef_sismico = 0.10
fraccion_Q_sismica = 0.50

lambda_G = 1.0
lambda_Q = 0.5
lambda_EX = 1.0
lambda_EY = 0.0
```

Estos valores corresponden al caso actual de trabajo. No necesariamente son
los valores definitivos que entregara el profesor.

Si el profesor entrega nuevos valores, se modifica solamente ese archivo. Por
ejemplo:

```python
q_Q = 3.0
coef_sismico = 0.20
fraccion_Q_sismica = 0.50
```

Luego se vuelve a ejecutar:

```powershell
python semana03\lab_semana03.py
```

El flujo es:

```text
Profesor entrega parametros
        ↓
editar semana03/parametros.py
        ↓
ejecutar lab_semana03.py
        ↓
revisar las verificaciones
```

`lab_semana03.py` importa explicitamente:

```python
from parametros import (
    q_Q,
    coef_sismico,
    fraccion_Q_sismica,
    lambda_G,
    lambda_Q,
    lambda_EX,
    lambda_EY,
)
```

Modificar `parametros.py` no modifica `benchmark_3d.py` ni los JSON guardados.
El benchmark es el modelo base existente; los parametros son entradas para
las verificaciones especiales de Semana 3.

El script valida automaticamente que:

* `q_Q` no sea negativo;
* `coef_sismico` no sea negativo;
* `fraccion_Q_sismica` este entre `0` y `1`.

Si una validacion falla, el script detiene el analisis y muestra un mensaje
claro.

## 4. Ejecucion principal

El comando principal es:

```powershell
python semana03\lab_semana03.py
```

Al comenzar, el script muestra los parametros activos:

```text
============================================================
SEMANA 3 - PARAMETROS DE LA ACTIVIDAD
============================================================

Carga viva q_Q               = 2.00 kN/m2
Coeficiente sismico Cs       = 0.10
Fraccion Q para masa sismica = 0.50

Combinacion:
1.00 G + 0.50 Q + 1.00 EX + 0.00 EY
```

Esto permite comprobar antes de interpretar los resultados que se estan
utilizando los valores correctos.

El script ejecuta tres bloques:

1. Parte A: carga viva Q.
2. Parte B: sismo pseudoestatico EX y EY.
3. Parte C: superposicion algebraica y corrida explicita.

## 5. Parte A — Carga viva Q

El modelo contiene un area tributaria para cada viga. Si `A_i` es el area
tributaria de la viga `i`, la carga transferida es:

```text
Q_i = q_Q * A_i
```

La conservacion de area se interpreta como:

```text
sum(A_i) = A_losa
```

Y la conservacion de carga como:

```text
sum(Q_i) = q_Q * A_losa
```

El script calcula la carga de todas las vigas con area tributaria positiva,
suma las areas, suma las cargas y muestra tambien la carga por nivel.

Despues ejecuta el caso Q en una copia del modelo y suma las reacciones
verticales `fz`:

```text
sum(Rz) aproximadamente igual a Q_total
```

Las dos comprobaciones no son iguales:

* La igualdad de areas y cargas verifica la transferencia de la losa hacia las
  vigas.
* La igualdad con las reacciones verifica el equilibrio global de OpenSees.

Si se conserva la carga total pero se reparte mal entre vigas, el equilibrio
global podria cerrar igualmente. Por eso se revisan tambien las areas
individuales.

## 6. Parte B — Sismo pseudoestatico EX y EY

La relacion fisica utilizada es:

```text
F = m*a
W = m*g
m = W/g
```

Si:

```text
a = Cs*g
```

entonces:

```text
F = (W/g)*(Cs*g)
F = Cs*W
```

El peso sismico por nivel se calcula como:

```text
W_sismico = G + fraccion_Q_sismica*Q
```

Con el valor base:

```text
W_sismico = G + 0.50Q
```

Esto no significa que el caso sismico sea una combinacion vertical `G + 0.5Q`.
Significa que se usa ese peso para estimar la masa que participa en la accion
sismica.

El corte basal es:

```text
V = coef_sismico * sum(W_i)
```

La fuerza de cada nivel se distribuye mediante:

```text
F_i = V * (W_i*h_i) / sum(W_j*h_j)
```

Donde `h_i` se mide desde la base del edificio.

Se construyen dos casos independientes:

```text
EX = sismo en direccion X
EY = sismo en direccion Y
```

Las fuerzas se aplican en los nodos maestros de los diafragmas. El script
verifica:

```text
sum(F_EX) = V_EX
sum(F_EY) = V_EY
sum(Rx) aproximadamente = -V_EX
sum(Ry) aproximadamente = -V_EY
```

Tambien muestra para el techo:

* `ux` y `uy`, para revisar la direccion de la deformacion;
* `rz`, para observar una posible torsion;
* la diferencia de rigidez entre X e Y.

El JSON historico del modelo no incluia la fraccion `0.5Q` en el peso
sismico. La correccion se realiza localmente en `lab_semana03.py`, usando una
copia en memoria. No se modifica la geometria, el benchmark ni los JSON.

## 7. Parte C — Superposicion lineal

Los casos independientes son:

```text
G
Q
EX
EY
```

La combinacion se controla con:

```text
R = lambda_G*G + lambda_Q*Q + lambda_EX*EX + lambda_EY*EY
```

Actualmente:

```text
R = 1.0G + 0.5Q + 1.0EX + 0.0EY
```

El script realiza dos calculos:

1. Superposicion algebraica de desplazamientos, reacciones y fuerzas internas
   obtenidos de los casos independientes.
2. Corrida explicita de OpenSees con las cargas combinadas aplicadas al mismo
   modelo en memoria.

La razon matematica es:

```text
K*u = F
u = K^-1*F
```

Si:

```text
F = F1 + F2
```

entonces:

```text
u = K^-1*(F1 + F2)
u = K^-1*F1 + K^-1*F2
u = u1 + u2
```

Se comparan:

* desplazamiento `ux` del techo;
* reaccion vertical `fz` de un apoyo;
* momento local `My` de una viga.

Se informan el valor por superposicion, el valor por corrida explicita, el
error absoluto y el error relativo.

La superposicion funciona porque el modelo de esta comprobacion es lineal
elastico. No debe aplicarse directamente cuando existan:

* materiales no lineales;
* plastificacion;
* daño;
* contacto;
* grandes deformaciones;
* rigidez dependiente del estado de la estructura.

## 8. Parte D — Capacidad de hormigon armado

Ejecutar por separado:

```powershell
python semana03\capacidad_ha.py
```

Este script estudia una seccion aislada y no modifica el modelo global.

La columna utilizada tiene dimensiones:

```text
0.50 x 0.50 m
```

La dimension coincide con la seccion de columna del modelo global.

Se revisaron las 38 laminas del proyecto `2017_67`. El edificio **no tiene
cuadro de pilares**: su sistema resistente son muros, y los elementos
verticales se detallan como cabezales de borde en las once elevaciones de eje
(`-300` a `-310`). La armadura longitudinal que aparece ahi es de muro
(`L:3+3f10` hasta `L:10+10f8`), que en una seccion de 0.50 x 0.50 m daria una
cuantia de 0.19 % a 0.40 %, bajo el minimo normativo de 1 %.

La armadura adoptada se toma del detalle tipico de pilar de la lamina
`2017_67-000`, "ESQUEMA ESTRIBOS EN VIGAS Y PILARES", cuya geometria se midio
directamente del DXF:

| Dato | Valor | Procedencia |
| --- | --- | --- |
| Numero de barras | 16, cinco por cara | lamina `2017_67-000` |
| Disposicion | perimetral | lamina `2017_67-000` |
| Estribos | 2E: exterior mas rombo interior | lamina `2017_67-000` |
| Espaciamiento de estribos | `phi10` a 10 cm | elevaciones `-300` a `-310` |
| Diametro longitudinal | `phi16` | **supuesto**; el edificio usa `phi16` a `phi28` |
| Recubrimiento | `50 mm` | supuesto |
| Acero | `fy = 420 MPa` | supuesto |
| Hormigon | `f'c = 28 MPa` | igual al modelo global |

Resulta `As = 32.17 cm2` y una cuantia de `1.29 %`. El unico dato inventado es
el diametro; todo lo demas es trazable a lamina. La seccion de 0.50 x 0.50 m
tampoco viene de plano: la fija `benchmark_3d.py` para las 82 columnas del
modelo.

## 9. Fiber Section

La seccion se divide en muchas regiones pequenas llamadas fibras. Cada fibra
contiene:

* area `A_i`;
* posicion `y_i`;
* material;
* deformacion `epsilon_i`;
* tension `sigma_i`.

La compatibilidad de deformaciones se expresa como:

```text
epsilon(y) = epsilon_0 - phi*y
```

Cada fibra recibe una deformacion y su material transforma esa deformacion en
una tension:

```text
sigma_i = f(epsilon_i)
```

La integracion de la seccion produce la carga axial y el momento:

```text
P = sum(sigma_i*A_i)
M = sum(sigma_i*A_i*y_i)
```

Las fibras de hormigon y acero tienen leyes constitutivas distintas. Por eso
la respuesta de la seccion puede representar la contribucion simultanea de
ambos materiales.

## 10. Curva M-phi

La curva momento-curvatura relaciona:

```text
M = momento
phi = curvatura
```

Permite observar:

* rigidez inicial aproximadamente lineal;
* cambio de rigidez;
* comportamiento no lineal;
* fluencia del acero si el rango de analisis la alcanza;
* capacidad maxima aproximada;
* comportamiento posterior, si el analisis lo representa.

El grafico se guarda en:

```text
semana03/resultados/momento_curvatura.png
```

## 11. Interaccion P-M

En una columna:

```text
P = carga axial
M = momento
```

La curva P-M representa combinaciones de carga axial y momento que la seccion
puede resistir bajo la hipotesis de compatibilidad de deformaciones.

La capacidad de momento depende de `P` porque la carga axial modifica el estado
de deformaciones y tensiones de las fibras. Por eso la seccion no tiene una
unica capacidad de momento independiente de la carga axial.

El grafico se guarda en:

```text
semana03/resultados/interaccion_PM.png
```

Para abrir los graficos desde PowerShell:

```powershell
explorer .\semana03\resultados
```

## 12. Resultados de referencia

Con los parametros actuales, la ejecucion de `lab_semana03.py` entrega:

```text
q_Q = 2.0000 kN/m2
Numero de vigas = 301
Area total = 4320.6505 m2
Q esperada = 8641.3010 kN
Q transferida = 8641.3010 kN
Reacciones Rz = 8641.3005 kN
Error relativo = 0.000006 %
OK
```

Para sismo:

```text
V_EX = 5497.2832 kN
V_EY = 5497.2832 kN
Equilibrio EX correcto
Equilibrio EY correcto
```

Para superposicion:

```text
Desplazamiento: OK
Reaccion: OK
Fuerza interna: OK
```

Con `capacidad_ha.py` se generan tres curvas M-phi (una por nivel de axial) y
una envolvente P-M de `56` puntos. En la corrida actual:

| Magnitud | Valor |
| --- | --- |
| M-phi con `P = 0` | `271.8 kN m` |
| M-phi con `P = 867 kN` (demanda mediana) | `390.3 kN m` |
| M-phi con `P = 3386 kN` (demanda maxima) | `457.1 kN m` |
| Traccion pura | `-1351.1 kN`, igual a `As*fy` |
| Punto balanceado | `535.4 kN m` con `2566.8 kN` |
| Compresion pura `Po` | `8196.7 kN` (cota) |

La traccion pura coincide exactamente con `As*fy`, y el momento que la
envolvente P-M entrega en `P = 0` coincide con el M-phi de flexion pura dentro
del 1 %: son dos caminos independientes que describen la misma seccion.

Estos numeros pueden cambiar si el profesor entrega otros parametros. La
interpretacion debe hacerse siempre junto con los valores mostrados al inicio
de la ejecucion.

## 13. Que ya existia antes de Semana 3

El proyecto ya contenia:

* geometria;
* nodos;
* vigas;
* columnas;
* muros;
* apoyos;
* propiedades estructurales;
* areas tributarias;
* carga permanente;
* carga viva;
* casos `G`, `Q`, `EX` y `EY`;
* resultados y equilibrio de OpenSees;
* conexion con Unity.

Semana 3 no reconstruye el edificio. Utiliza esa informacion para realizar
verificaciones nuevas y una demostracion de capacidad de seccion.

## 14. Limitaciones y supuestos

* `Cs` es un coeficiente pseudoestatico de trabajo, no un analisis completo de
  NCh433.
* La fraccion de carga viva incluida en el peso sismico se controla desde
  `parametros.py`.
* La correccion de `G + 0.5Q` se realiza en memoria y no modifica el benchmark.
* De la armadura de la Parte D, el numero de barras, la disposicion y la
  topologia de estribos se midieron de la lamina `2017_67-000`; solo el
  diametro longitudinal es supuesto.
* La superposicion se demuestra en el modelo elastico lineal existente.
* La Parte D no representa automaticamente la capacidad no lineal de todas las
  columnas del edificio.

## 15. Mensaje para la defensa oral

La idea central que todos los integrantes deben poder explicar es:

> En Semana 3 utilizamos el modelo estructural ya desarrollado para verificar
> la transferencia de cargas, estudiar la respuesta sismica, demostrar la
> superposicion en el regimen lineal y comenzar a estudiar la capacidad no
> lineal de una seccion de hormigon armado.

La respuesta corta por parte es:

| Parte | Que hacemos | Que demostramos |
| --- | --- | --- |
| A | Repartimos la carga viva por areas tributarias. | Conservacion de carga y equilibrio vertical. |
| B | Aplicamos fuerzas sismicas independientes en X e Y. | Corte basal, equilibrio y respuesta lateral. |
| C | Combinamos G, Q, EX y EY de dos maneras. | Superposicion en el regimen lineal. |
| D | Analizamos una seccion HA con fibras. | Capacidad M-phi e interaccion P-M. |
