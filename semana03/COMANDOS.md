# Chuleta de comandos — Semana 3

Todo desde la raíz del repo. Los tres edificios son `ingenieria`, `lt2`
y `conjunto`; si no se dice cuál, es `ingenieria`.

---

## 0. Si solo alcanzas a correr una cosa

```powershell
python comun\verificar_todo.py
```

Corre la suite entera —los tests, las tres partes en los dos edificios,
capacidad, demanda y el anexo de Unity— y termina en `26 de 26 EN OK`.
Tarda unos 15 s.

---

## 1. Partes A, B y C — el laboratorio

```powershell
python semana03\lab_semana03.py
python semana03\lab_semana03.py lt2
python semana03\lab_semana03.py conjunto
```

**Qué hace:** construye en memoria los casos Q, EX y EY con los
parámetros del profesor, los resuelve con OpenSees y verifica las tres
partes. No toca nada de `data/`.

- **[A]** carga viva: reconstruye Q a `q_Q` en cada elemento y compara lo
  aplicado contra las reacciones.
- **[B]** sismo: peso sísmico, reparto en altura, corte basal, sentido de
  la deformada y torsión de piso.
- **[C]** superposición: los tres números del enunciado, y además **todos**
  los grados de libertad contra la corrida explícita.

Termina en `LAS TRES PARTES CIERRAN`. ~1 s por edificio.

---

## 2. Si el profesor dicta parámetros

**No se edita ningún archivo.** Van como argumentos, en cualquier script:

```powershell
python semana03\lab_semana03.py --q 2.5 --cs 0.20
python semana03\lab_semana03.py --patron potencia --k 2
python semana03\lab_semana03.py --patron manual --fracciones 5 10 20 30 35
python semana03\lab_semana03.py --comb 1.2 1.0 1.4 0
```

| Bandera | Qué cambia |
| --- | --- |
| `--q` | carga viva, kN/m² |
| `--cs` | coeficiente sísmico (NCh433 daría `0.20`) |
| `--fq` | fracción de Q en el peso sísmico |
| `--k` | reparto en altura: `0` uniforme, `1` triangular, `2` NCh433 |
| `--patron manual --fracciones …` | reparto dictado, se normaliza solo |
| `--comb G Q EX EY` | los cuatro factores de la combinación |

Para ver qué quedaría, sin correr el análisis:

```powershell
python semana03\parametros.py --q 2.5 --cs 0.20 --k 2
```

---

## 3. Parte D — capacidad de hormigón armado

```powershell
python comun\capacidad.py ingenieria 18 --pm --mphi --dibujo
```

**Qué hace:** arma la Fiber Section de esa columna leyendo el modelo
(dimensiones, `f'c`, enfierradura) con confinamiento de Mander, y saca:

- `--pm` la curva P-M **interpretada** (tracción pura, nariz, compresión pura)
- `--mphi` el gráfico M-φ a 0, 15, 30 y 50 % de la compresión pura
- `--dibujo` la discretización: cada fibra, su material, cada barra

```powershell
python semana03\demanda_capacidad.py ingenieria 18 --grafico --mphi
python semana03\demanda_capacidad.py ingenieria --lista
python semana03\demanda_capacidad.py ingenieria --todas
```

**Qué hace:** pone la demanda `(P, M)` de esa columna en G, Q, EX y EY
**sobre su propia curva** y da la utilización. `--lista` muestra qué
elementos tienen fierro; `--todas` revisa las 82 columnas.

```powershell
python semana03\verificar_rc.py ingenieria 18
```

**Qué hace:** calcula los puntos característicos **a mano** con el bloque
de Whitney y los compara con la Fiber Section, explicando cada
diferencia (el 0.85 de ACI, el endurecimiento, el confinamiento).

Para el LT2: `lt2 1` es una columna, `lt2 9` un muro.

---

## 4. Las verificaciones, sueltas

```powershell
python comun\sismo.py ingenieria EY --detalle
```
Carga aplicada contra corte basal, centro de rigidez, y por piso el
desplazamiento, el giro y el **cociente de torsión** de NCh433.

```powershell
python comun\combinar.py ingenieria
```
Superposición contra la corrida explícita, sobre **todos** los grados de
libertad, con la cota de redondeo del motor como criterio.

```powershell
python comun\verificar_tributarias.py ingenieria
```
El reparto de losa contra el dibujo del visor, piso por piso.

```powershell
python semana03\verificar_viga_partida.py
python semana03\verificar_viga_partida.py 352
```
Demuestra, refinando la malla, que **partir una viga no es lo que la
hunde**. Sale idéntico con 2, 4, 8 y 16 tramos.

---

## 5. Unity

```powershell
python semana03\exportar_unity.py ingenieria
```
Deja las cargas, la deformada sísmica y la enfierradura en el JSON que
lee el visor. Acepta los mismos parámetros que el laboratorio.

En Play, todo se maneja desde el panel:

```
--- deformada ---     [Sin deformar] [Cargas G] [Sismo EX] [Sismo EY]
--- Semana 3 ---      [x] Flechas de carga    [G][Q][EX][EY][COMB]
                      [x] Enfierradura        [x] todas  [ ] lámina ampliada
```

Las flechas aparecen al elegir una deformada de **sismo**.

---

## 6. Rehacer el modelo desde cero

Solo si hace falta; el modelo ya está armado y calculado.

```powershell
python edificios\ingenieria\armar.py      # planos -> data/modelo/
python comun\calcular.py ingenieria       # -> data/resultados/
```

---

## Los cuatro números que conviene tener en la cabeza

| | |
| --- | --- |
| Parte A | 4320.65 m², 8641.30 kN; reacciones a `2e-8` |
| Parte B | V = 5497.28 kN; torsión **extrema** bajo EY en los 3 pisos altos |
| Parte C | 9102 valores comparados, todos bajo la cota de redondeo |
| Parte D | columna 18: 16 φ16, cuantía 1.29 %, nariz en 2478 kN / 427 kN·m |
