# Semana 3 — Cómo correr

Carga viva, sismo pseudoestático, superposición y capacidad de hormigón
armado, sobre cualquiera de los tres edificios del repositorio. El
informe con los resultados y su interpretación está en
[`reports/semana03.md`](../reports/semana03.md); la guía de estudio para
la defensa, en [`GUIA_SEMANA3.md`](GUIA_SEMANA3.md); y la chuleta de
comandos para tener a mano, en [`COMANDOS.md`](COMANDOS.md). Este archivo
dice qué hay y cómo se corre.

## Qué hay en esta carpeta

| Archivo | Qué hace |
| --- | --- |
| `lab_semana03.py` | Partes A, B y C: construye Q, EX y EY en memoria con los parámetros del profesor, los resuelve y verifica. |
| `parametros.json` | Los parámetros que define el profesor, con su justificación. |
| `parametros.py` | Los lee y deja sobreescribirlos por línea de comandos. |
| `demanda_capacidad.py` | Parte D: pone la demanda de una columna o muro sobre su propia curva P-M. |
| `verificar_rc.py` | Parte D: la Fiber Section contra el cálculo a mano del curso (Whitney). |
| `verificar_viga_partida.py` | Comprueba, refinando la malla, que partir una viga en el nodo donde llega la perpendicular no es lo que la hunde. |
| `exportar_unity.py` | Deja cargas, deformada y enfierradura en un JSON para el visor. |
| `resultados/` | Las figuras que generan los scripts de arriba. |

Los cálculos viven en `comun/` y sirven a los tres edificios:

| Módulo | Qué hace |
| --- | --- |
| `comun/capacidad.py` | Fiber Section, M-phi, P-M, discretización dibujada. Una sola definición de la sección para todo. |
| `comun/sismo.py` | Revisa un caso lateral: carga, corte basal, sentido de la deformada, torsión de piso. |
| `comun/combinar.py` | Superposición sobre todos los grados de libertad, contra la corrida explícita. |
| `comun/verificar_tributarias.py` | El reparto de losa contra el dibujo, piso por piso. |

La enfierradura de las columnas del edificio de Ingeniería la pega
`edificios/ingenieria/enfierradura.py` en la etapa de armado; ahí está
explicado de dónde sale y qué parte es supuesta. La del LT2 se lee de
sus elevaciones en `edificios/lt2/planos/enfierradura.py`.

## Requisitos

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Los modelos ya están armados en `data/modelo/` y sus resultados en
`data/resultados/`. Ninguno de los scripts de esta carpeta los modifica.

## 1. El laboratorio: Partes A, B y C

```powershell
python semana03\lab_semana03.py                # edificio de Ingeniería
python semana03\lab_semana03.py lt2
python semana03\lab_semana03.py conjunto
```

Imprime los parámetros con los que corre, y después:

- **[A]** cuántos elementos reciben losa y por qué vía, con qué
  intensidad venía el caso Q del modelo, la reconstrucción a `q_Q`,
  `q_Q * A`, la carga aplicada y las reacciones de OpenSees.
- **[B]** el peso sísmico y la fuerza por nivel, el corte basal, y para
  EX y EY la revisión de `comun/sismo.py`: carga contra reacciones,
  centro de rigidez, y por piso el desplazamiento, el movimiento fuera de
  la dirección empujada, el giro y el cociente de torsión.
- **[C]** los tres números del enunciado (un desplazamiento, una reacción,
  una fuerza interna) por superposición y por corrida explícita, y la
  comparación sobre todos los grados de libertad del modelo con su cota
  de redondeo.

Termina con `LAS TRES PARTES CIERRAN` o con la lista de lo que no cierra.

## 2. Los parámetros del profesor

Viven en `parametros.json`. Cualquiera se sobreescribe por línea de
comandos, en cualquiera de los scripts:

| Bandera | Qué cambia | Ejemplo |
| --- | --- | --- |
| `--q` | intensidad de carga viva, kN/m² | `--q 2.5` |
| `--cs` | coeficiente sísmico, fracción de g | `--cs 0.20` |
| `--fq` | cuánta Q entra al peso sísmico | `--fq 0.25` |
| `--patron` | `potencia` o `manual` | `--patron manual` |
| `--k` | exponente del patrón `potencia`: 0 uniforme, 1 triangular, 2 NCh433 | `--k 2` |
| `--fracciones` | reparto manual de abajo hacia arriba; se normaliza solo | `--fracciones 5 10 20 30 35` |
| `--comb` | los cuatro factores de la combinación: G Q EX EY | `--comb 1.2 1.0 1.4 0` |
| `--combinacion` | una de las declaradas en el JSON | `--combinacion 1.2G+1.6Q` |

```powershell
python semana03\lab_semana03.py ingenieria --cs 0.20 --k 2
python semana03\lab_semana03.py lt2 --patron manual --fracciones 5 10 20 30 35
python semana03\parametros.py --q 3 --comb 1.2 1.6 0 0      # solo muestra qué quedaría
```

Un valor sin sentido físico (q negativo, fracción fuera de 0–1, patrón
desconocido, fracciones con otro número de niveles) detiene el script con
el mensaje de qué está mal.

## 3. Parte D: capacidad de hormigón armado

La sección se lee del modelo: dimensiones de `secciones`, `f'c` del
material, y la enfierradura que trae el elemento. El confinamiento sale
del estribo con Mander; no es un número puesto a mano.

```powershell
# la seccion de la columna 18: M-phi, P-M interpretada, M-phi a varios
# axiales y la discretizacion dibujada
python comun\capacidad.py ingenieria 18 --pm --mphi --dibujo

# su demanda en G, Q, EX y EY sobre su propia curva, con grafico, y las
# M-phi a los axiales que le pone cada caso
python semana03\demanda_capacidad.py ingenieria 18 --grafico --mphi
python semana03\demanda_capacidad.py ingenieria --lista        # que elementos tienen fierro
python semana03\demanda_capacidad.py ingenieria --todas        # las 82 columnas

# la Fiber Section contra el calculo a mano del curso
python semana03\verificar_rc.py ingenieria 18
```

Para el LT2 lo mismo con `lt2 1` (columna) o `lt2 9` (muro). Las figuras
quedan en `resultados/`:

| Figura | Qué muestra |
| --- | --- |
| `fibras_<edificio>_<elem>.png` | la discretización: cada fibra, su material, cada barra |
| `mphi_<edificio>_<elem>.png` | M-phi a 0, 15, 30 y 50 % de la compresión pura |
| `mphi_<edificio>_<elem>_demanda.png` | M-phi a los axiales que le pone la demanda |
| `pm_<edificio>_<elem>.png` | la curva P-M con los puntos de demanda encima |

## 4. Unity

```powershell
python semana03\exportar_unity.py ingenieria        # acepta los mismos parametros
```

Deja `data/unity/semana03.json` y una copia en
`unity/Assets/StreamingAssets/`. El visor lo lee con `VisorSemana03.cs`,
que ya está en la escena `SampleScene`. Lo que se exporta es lo que el
laboratorio corre con esos parámetros, no lo guardado en
`data/resultados/`.

### Todo se maneja desde el panel en pantalla

Al dar Play aparece el panel de siempre (`VisorQA`), con dos secciones
nuevas abajo:

```
--- deformada ---
[> Sin deformar] [Cargas G]
[Sismo EX]       [Sismo EY]
escala grafica x300   [slider]  [x1][x100][x500][x1000]

--- Semana 3 ---
[x] Flechas de carga
    [G] [Q] [> EX] [EY] [COMB]
[x] Enfierradura
    [x] en todas las columnas   [ ] lamina ampliada
```

**La deformada tiene una sola fuente a la vez.** `Cargas G` son los
`ux/uy/uz` que el JSON del modelo trae precalculados; `Sismo EX` y
`Sismo EY` salen del anexo de Semana 3. Elegir uno apaga el otro, así
que los dos scripts no se pelean por quién manda.

**Las flechas aparecen al elegir una deformada de sismo**, y son las del
caso que la produce. Se dibujan **al costado del edificio**, no sobre su
punto de aplicación: ahí adentro tapan justo lo que uno quiere mirar. Se
corren en bloque, así que conservan sus posiciones relativas y se siguen
leyendo como un diagrama. Con un caso sísmico son cinco flechas en una
franja angosta —el diagrama de fuerza lateral de toda la vida—; con `G`
o `Q` son cientos repartidas por la planta, así que la nube queda tan
ancha como el edificio, pero al lado.

**La enfierradura** va por defecto en las 82 columnas, y sigue la
deformada. La *lámina ampliada* —la jaula a 6× al costado, que es la
única forma de ver las barras y los estribos de verdad— viene apagada:
a escala del edificio parece una columna gigante flotando.

En el Inspector del objeto `VisorSemana03` hay ajustes finos que no
están en el panel: `separacionCargas` y `cargasAlCostado` (dónde van las
flechas), `cargasConLaDeformada` (para dejarlas siempre visibles),
`umbralPorcentaje` (filtra las chicas de `G` y `Q`), `escalaDetalle` y
`exageracionBarra`. Todos se aplican en caliente, sin salir de Play.

## 5. Las vigas que se ven hundidas

En el visor hay vigas que se hunden en el medio, justo donde están
partidas en dos elementos. El corte no es la causa, y comprobarlo es
refinar la malla: si lo fuera, poner más tramos cambiaría la respuesta.

```powershell
python semana03\verificar_viga_partida.py              # el nodo 373
python semana03\verificar_viga_partida.py 352          # otro nodo
python semana03\verificar_viga_partida.py lt2 33
```

Sale idéntico al cuarto decimal con 2, 4, 8 y 16 tramos. Lo que la hunde
es la viga perpendicular que aterriza ahí con su losa y sin columna
debajo: 85 % de la flecha en el nodo 373. Y la flecha es `L/1527`, muy
lejos del `L/360` de la norma — lo que se ve grande es la escala gráfica
×300 del visor. Sin argumento, `python ... verificar_viga_partida.py lt2`
lista los nodos que sí son punto medio de una viga partida.

## 6. Las verificaciones, solas

Los módulos de `comun/` corren también sobre `data/resultados/`, para
revisar un edificio sin pasar por el laboratorio:

```powershell
python comun\sismo.py ingenieria EY --detalle
python comun\combinar.py ingenieria
python comun\verificar_tributarias.py
```

## 7. Qué esperar

Con los parámetros por defecto (`q_Q = 2.0`, `Cs = 0.10`, `f = 0.5`,
`k = 1`, combinación `1.0 G + 0.5 Q + 1.0 EX`), los tres edificios
cierran las tres partes. Los números están en el informe; en resumen,
para el edificio de Ingeniería:

| | |
| --- | --- |
| Parte A | 301 vigas, 4320.65 m², 8641.30 kN; reacciones a 2e-8 relativo |
| Parte B | V = 5497.28 kN; corte basal cierra a 1e-4 kN; torsión extrema en el nivel +7.92 bajo EX y en los tres superiores bajo EY |
| Parte C | 9102 valores comparados; el peor desacuerdo queda bajo la cota de redondeo del motor |
| Parte D | columna 18: 16 phi16, cuantía 1.29 %, f'cc = 39.4 MPa; nariz de la P-M en 2478 kN y 427 kN m |

Los números cambian con los parámetros. Lo que no cambia es que las
verificaciones tienen que cerrar.
