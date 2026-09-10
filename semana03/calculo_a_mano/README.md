# Cálculo a mano

Lo que se calculó **fuera del código**, para contrastar contra la Fiber
Section de `comun/capacidad.py`. Un cálculo hecho aparte, con otro método
y por otra persona, es la única forma de cazar un error que el código
comete de manera consistente.

| archivo | qué es |
| --- | --- |
| `interaccion_columna18.xlsx` | Diagrama de interacción de la columna 18 por el método del curso (ACI, bloque de Whitney), con los siete puntos característicos y sus factores `φ`. |

## `interaccion_columna18.xlsx`

Hoja `Elemento 18`. Toma `f'c = 28 MPa`, `b = h = 500 mm`, `fy = 420 MPa`,
`ε_cu = 0.003`, `β₁ = 0.85` y las 16 φ16 (`Ast = 3216.99 mm²`), y arma la
curva punto por punto iterando la profundidad del eje neutro `c`:

| punto | `c` [mm] | `Pn` [kN] | `Mn` [kN·m] | `φ` | `φPn` | `φMn` |
| --- | --- | --- | --- | --- | --- | --- |
| a. compresión pura | — | 7224.57 | 0 | 0.65 | 3756.78 | 0 |
| b. deformación inferior nula | 350 | 4013.15 | 480.38 | 0.65 | 2608.55 | 312.25 |
| c. balance | 260 | 2659.13 | 540.98 | 0.65 | 1728.44 | 351.64 |
| d. transición | 221 | 2135.69 | 525.12 | 0.733 | 1566.17 | 385.08 |
| e. última falla dúctil | 163.7 | 1337.49 | 471.25 | 0.90 | 1203.74 | 424.12 |
| f. flexión pura | 76.6 | 0 | 279.13 | 0.90 | 0 | 251.22 |
| g. tracción pura | — | −1351.14 | 0 | 0.90 | −1216.02 | 0 |

**Trae los factores `φ`, que el repositorio no.** `comun/capacidad.py`
calcula capacidad **nominal**: la curva de diseño `φPn`–`φMn` sale solo
de acá. Es la diferencia entre "qué aguanta la sección" y "con qué se
diseña", y son dos curvas distintas.

## Contra la Fiber Section

`python comun/capacidad.py ingenieria 18 --pm`

| punto | Excel | fibras | diferencia |
| --- | --- | --- | --- |
| tracción pura | −1351.14 kN | −1351.1 kN | **0.003 %** |
| compresión pura | 7224.57 kN | 8261.1 kN | −12.5 % |
| flexión pura, `Mn` | 279.13 kN·m | 256.5 kN·m | 8.8 % |
| momento máximo de la curva | 540.98 (en `P` = 2659) | 426.6 (en `P` = 2478) | — |

Las dos primeras son las que **tienen** que coincidir o explicarse:

- **Tracción pura coincide al tercer decimal.** Es `As·fy` y no hay
  hipótesis distintas. Confirma que las dos secciones tienen el mismo
  acero.
- **Compresión pura es exactamente el 0.85 de ACI.** El Excel usa
  `0.85 f'c` y las fibras `f'c`. Rehecho con `f'c`, el cálculo a mano da
  8261.1 kN — el 100.00 % del de fibras. `verificar_rc.py` lo comprueba
  solo, y da **7224.6 kN**: el mismo número que el Excel, por dos
  caminos independientes.

## Por qué el resto no coincide, y está bien

**El Excel agrupa las barras en cuatro capas; la sección real tiene
cinco.**

```
Excel    d =  58 (5 barras) · 186 (3) · 314 (3) · 442 (5)   = 16
fibras   d =  68 (5 barras) · 159 (2) · 250 (2) · 341 (2) · 432 (5) = 16
```

Dos diferencias, las dos hacia el mismo lado:

1. **El recubrimiento.** El Excel pone la primera fila a 58 mm; las
   fibras la ponen a 68, porque descuentan también el estribo φ10
   (`50 + 10 + 16/2 = 68`). Eso le da al Excel 10 mm más de brazo en
   cada cara.
2. **La agrupación.** Las seis barras intermedias van en el Excel en dos
   filas de tres, y en la realidad en tres filas de dos —una de ellas
   justo en el centroide, donde no aporta momento.

Las dos suben el momento del Excel, y por eso su flexión pura da 8.8 %
más. `verificar_rc.py`, que también agrupa pero con el recubrimiento
completo, da 273.4 kN·m — entre los dos, como corresponde.

## Las demandas de la hoja

La tabla de demandas (columna J) son las de la columna 18 en los cuatro
casos, **a los mismos parámetros del informe** — `q_Q = 3.0 kN/m²` de
NCh1537 Of.2009 Tabla 4:

| caso | M [kN·m] | P [kN] |
| --- | --- | --- |
| G | 34.6468 | 3385.9176 |
| Q | 10.6268 | 1026.7221 |
| EX | 18.4932 | 5.4977 |
| EY | 38.7084 | 58.2682 |

Salen de:

```powershell
python semana03\demanda_capacidad.py ingenieria 18
```

Si se cambia `q_Q`, `Cs` o el patrón en altura, `G` no se mueve —no
depende de la sobrecarga— pero `Q`, `EX` y `EY` sí, y hay que traerlas de
nuevo.

## Al editar la hoja

Guardarla con `openpyxl` **conserva las fórmulas pero borra los valores
calculados**: Excel los repone al abrir, pero mientras tanto un visor que
no recalcule muestra las celdas vacías. Si se edita por script, conviene
recalcular después:

```python
import win32com.client as w
app = w.DispatchEx('Excel.Application'); app.Visible = False
wb = app.Workbooks.Open(ruta_absoluta)
app.CalculateFullRebuild(); wb.Save(); wb.Close(); app.Quit()
```
