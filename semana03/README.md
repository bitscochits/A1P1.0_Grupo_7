# Semana 3

Esta entrega reutiliza el modelo existente del Edificio de Ingenieria. No
reconstruye la geometria: lee `data/modelo/ingenieria.json`, los resultados
guardados y usa el motor comun de OpenSees en memoria.

## 1. Preparar el entorno

Abrir PowerShell y entrar a la raiz del repositorio personal:

```powershell
cd C:\Users\mcubi\A1P1.0_Grupo_7_semana3
```

Comprobar que estamos en la carpeta correcta:

```powershell
Get-Location
Test-Path .\data\modelo\ingenieria.json
Test-Path .\semana03\lab_semana03.py
```

Los dos comandos `Test-Path` deben responder `True`. El trabajo se realiza
solo en este repositorio y no necesita modificar el repositorio grupal.

Si las dependencias no estan instaladas, crear un entorno virtual e instalar
las del proyecto:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

La activacion del entorno se repite cada vez que se abre una nueva terminal:

```powershell
.\.venv\Scripts\Activate.ps1
```

## 2. Ejecutar la demostracion principal

Comando completo:

```powershell
python semana03\lab_semana03.py
```

El script realiza tres bloques, en este orden:

1. Carga viva Q.
2. Sismo pseudoestatico EX y EY.
3. Superposicion y corrida explicita.

No genera un nuevo `ingenieria.json` ni sobrescribe los resultados globales.

## 3. Parte A: carga viva Q

El script lee `w_live_val` desde `edificios/ingenieria/benchmark_3d.py` y
lee las areas `area_tributaria` desde `data/modelo/ingenieria.json`.

Para cada viga calcula:

```text
Q_i = q_Q * A_i
```

Luego verifica la conservacion global:

```text
Q_transferida = sum(Q_i) = q_Q * sum(A_i)
```

Finalmente lee `data/resultados/ingenieria_Q.json` y suma sus reacciones `fz`.
La diferencia entre `Q_transferida` y `sum(Rz)` es el error de equilibrio.

La salida importante es:

```text
Area total
Q esperada
Q transferida
Reacciones Rz
Error absoluto
Error relativo
```

`OK` significa que el error relativo es menor que `0.01 %`.

## 4. Parte B: sismo EX y EY

Los casos EX y EY son independientes y se aplican en los nodos maestros de
los diafragmas. La demostracion usa el peso sismico:

```text
W_i = G_i + 0.5 Q_i
V = Cs * sum(W_i)
F_i = V * W_i * h_i / sum(W_j * h_j)
```

`Cs` se lee desde el valor existente `COEF_SISMICO` del modelo. Actualmente
es `0.10`; no se inventa un coeficiente nuevo.

El JSON historico del proyecto no incluia `0.5 Q` en el peso sismico. La
correccion se aplica localmente dentro de `lab_semana03.py`, sin cambiar la
geometria, los JSON ni los resultados existentes.

El script verifica que:

```text
sum(F_EX) = V_EX
sum(F_EY) = V_EY
sum(Rx) aproximadamente = -V_EX
sum(Ry) aproximadamente = -V_EY
```

Tambien muestra `ux`, `uy` y `rz` del techo. En EX debe dominar `ux`; en EY
debe dominar `uy`. `rz` permite observar la torsion del diafragma.

## 5. Parte C: superposicion

La combinacion usada en la demostracion esta declarada en un solo lugar del
script:

```text
1.0 G + 0.5 Q + 1.0 EX
```

Se hacen dos calculos:

1. **Superposicion algebraica:** combina los desplazamientos, reacciones y
   fuerzas internas de los casos independientes.
2. **Corrida explicita:** aplica las cargas combinadas simultaneamente en una
   nueva resolucion OpenSees en memoria.

Se comparan tres cantidades:

- desplazamiento `ux` del nodo maestro del techo;
- reaccion vertical `fz` de un apoyo;
- momento local `My` de una viga.

La igualdad se espera porque el modelo es lineal elastico:

```text
K u = F
u(lambda_1 F_1 + lambda_2 F_2) = lambda_1 u_1 + lambda_2 u_2
```

Esta propiedad no debe utilizarse sin mas en un analisis no lineal.

## 6. Parte D: capacidad de hormigon armado

Ejecutar:

```powershell
python semana03\capacidad_ha.py
```

Este script no modifica el modelo global. Estudia por separado una columna de

La armadura no aparece en los datos del proyecto. Por eso se declara de forma
visible como:

```text
SUPUESTO DE LABORATORIO - NO EXTRAIDO DE PLANOS
```

El supuesto usado es diez barras de 20 mm, recubrimiento de 50 mm y acero de
420 MPa.

La Fiber Section divide la seccion en fibras de hormigon y acero. Cada fibra
recibe una deformacion:

```text
epsilon(y) = epsilon_0 - phi * y
```

Cada deformacion se transforma en tension mediante la ley constitutiva del
material. La integracion de la seccion es:

```text
P = sum(sigma_i * A_i)
M = sum(sigma_i * A_i * y_i)
```

La curva M-phi muestra la respuesta de la seccion al aumentar la curvatura.
La curva P-M muestra que la capacidad a flexion cambia cuando cambia la carga
axial.

## 7. Archivos generados

La ejecucion de capacidad crea o reemplaza:

```text
semana03/resultados/momento_curvatura.png
semana03/resultados/interaccion_PM.png
```

Para abrir la carpeta de resultados desde PowerShell:

```powershell
explorer .\semana03\resultados
```

## 8. Como leer la entrega

**Demanda:** `G`, `Q`, `EX`, `EY` y sus combinaciones representan las cargas
que actuan sobre el edificio global.

**Capacidad:** Fiber Section, M-phi e interaccion P-M representan la capacidad
aproximada de una seccion aislada de columna.

Un resultado `OK` indica que la comprobacion numerica programada se cumple;
no significa por si solo que el edificio completo este disenado para todas
las exigencias normativas.

## 9. Archivos principales consultados

- `edificios/ingenieria/benchmark_3d.py`: cargas, secciones y `Cs`.
- `data/modelo/ingenieria.json`: nodos, elementos, diafragmas y areas.
- `data/resultados/ingenieria_Q.json`: reacciones del caso Q.
- `comun/servidor_opensees.py`: motor comun de OpenSees.
- `semana03/lab_semana03.py`: Partes A, B y C.
- `semana03/capacidad_ha.py`: Parte D.
