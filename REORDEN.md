# El repo se reordenó — léelo antes de hacer `pull`

> **Pásale este archivo a tu Claude antes de pedirle algo.** Está escrito
> para que entienda de una qué cambió y por qué, sin tener que
> redescubrirlo.

Grupo 7 · Laboratorio estructural digital
Repo: `https://github.com/bitscochits/A1P1.0_Grupo_7`
Commits: `6d2fff3` (merge de las dos ramas) y `45def0e` (el reorden).

---

## 1. Lo primero, para no perder trabajo

```bash
git status          # si aparece algo modificado, commitealo AHORA
git add -A && git commit -m "mi trabajo antes del reorden"
git pull
```

Se movieron ~40 archivos, pero **git los registró como renombres**, así
que el `pull` los aplica solo. Lo único que puede chocar es trabajo sin
commitear sobre un archivo que se movió. Por eso: commit primero.

Después del `pull`, borrá los `__pycache__` viejos por si acaso:

```bash
find . -name __pycache__ -type d -not -path './unity/*' -exec rm -rf {} +
```

---

## 2. Qué pasó, en una frase

Las dos mitades del proyecto venían creciendo separadas y sin saber una
de la otra. **Se juntaron en una sola rama, y el repo se ordenó por
edificio para que cada uno pueda trabajar sin pisar al otro.**

---

## 3. Dónde quedó tu código

Nada se borró ni se renombró. **Solo cambió de carpeta.**

| antes (raíz) | ahora |
|---|---|
| `benchmark_3d.py` | `edificios/ingenieria/benchmark_3d.py` |
| `export_unity.py` | `edificios/ingenieria/export_unity.py` |
| `verificar_planos.py` | `edificios/ingenieria/verificar_planos.py` |
| `test_contrato_unity.py` | `edificios/ingenieria/test_contrato_unity.py` |
| `modelo_benchmark.py` | `benchmark/modelo_benchmark.py` |
| `benchmark_distribuida.py` | `benchmark/benchmark_distribuida.py` |
| `generar_json_unity.py` | `benchmark/generar_json_unity.py` |
| `test_areas_tributarias.py` | `benchmark/test_areas_tributarias.py` |
| `error_section.py`, `error_support.py` | `benchmark/` |
| `servidor_opensees.py` | `comun/servidor_opensees.py` |
| `modelo_unity_edificio.json` | `data/unity/ingenieria.json` |
| `modelo_unity.json` (el del benchmark) | `data/unity/benchmark.json` |
| `test_servidor.py` | se quedó en la raíz |

**Tus comandos, actualizados:**

```bash
python edificios/ingenieria/benchmark_3d.py      # modelo + 4 casos + equilibrio
python edificios/ingenieria/export_unity.py      # -> data/unity/ingenieria.json
python edificios/ingenieria/verificar_planos.py  # contra los DXF
python edificios/ingenieria/test_contrato_unity.py
python comun/servidor_opensees.py                # el servidor
python benchmark/benchmark_distribuida.py
python test_servidor.py
```

Los ajustes de `sys.path` y de rutas ya están hechos. **Los corrí todos
después de mover: los ocho pasan.** `verificar_planos.py` sigue pidiendo
los DXF en `C:\dxf_planos\`; si no están, avisa y no falla, igual que antes.

`modelo_benchmark.py` se fue a `benchmark/` pero sigue siendo la física
compartida (`J_rectangular`, `area_tributaria_viga`): `benchmark_3d.py`
lo importa igual que siempre, ahora agregando esa carpeta a `sys.path`.

---

## 4. Cómo quedó ordenado el repo

```
edificios/
  ingenieria/   TUYO      el cuerpo antiguo   (planos 2017_67)
  lt2/          DE PEDRO  el cuerpo nuevo     (planos 2024_22)
  conjunto/     DE LOS DOS   los dos unidos por la junta

comun/          DE LOS DOS   acordar antes de tocar
  rutas.py             dónde está cada cosa
  contrato.py          qué es un "modelo"
  calcular.py          la etapa de cálculo, genérica
  servidor_opensees.py el servidor Flask
  lanzar_unity.py      compila y abre el visor

benchmark/      el benchmark de Semana 1 (UZ = −0.06348 mm)

data/
  geometria/    lo que dice el plano
  modelo/       listo para calcular
  resultados/   lo que OpenSees calculó
  unity/        lo que dibuja el visor

unity/          DE LOS DOS   un solo visor para los tres edificios
```

**Regla: una carpeta, un dueño.** Si necesitás algo de la otra mitad, se
pide por el JSON de `data/modelo/`, no importando su código.

---

## 5. El descubrimiento: son el mismo edificio

Esto no lo sabíamos y salió al comparar los dos modelos.

| | Ingeniería (`2017_67`) | LT2 (`2024_22`) |
|---|---|---|
| Cotas de piso | −7.97 · −4.01 · −0.05 · +3.91 · +7.87 · +11.83 | **las mismas**, más el −8.57 |
| Altura de piso | 3.96 m | 3.96 m |

Extraídas por separado, de dos juegos de planos distintos, por dos
personas distintas. **Coinciden.** Y en los planos del LT2 tu zona
aparece rotulada como **"ETAPA ANTERIOR"**.

Son **dos etapas del mismo edificio, separadas por una junta de
dilatación** en `x = 42.75` — que es justo donde Pedro corta su ventana
de extracción.

Lo que **falta** para poder unirlos está en
`edificios/conjunto/README.md`, y son dos cosas:

1. **Que tu edificio también emita `data/modelo/ingenieria.json`.** Ver
   el punto 7.
2. **El calce entre los dos sistemas de coordenadas.** En vertical ya
   calzan. En planta no: tus ejes X van 8.02–53.02 y los suyos
   10.96–43.75; los Y tuyos 47.70–72.75 y los suyos 11.05–37.92. Son
   coordenadas de página de láminas distintas, no de terreno. Hay que
   **medir** la transformación sobre algo que aparezca en los dos
   juegos de planos — lo mejor es la junta de dilatación misma.

---

## 6. El pipeline nuevo

```
   planos DXF
      │   ingesta            propia de cada edificio
      ▼
   data/geometria/<edificio>.json      lo que DICE el plano
      │   armado             propia de cada edificio
      ▼
   data/modelo/<edificio>.json         listo para calcular  ◄── el contrato
      │   cálculo            comun/calcular.py, uno solo
      ▼
   data/resultados/<edificio>_<caso>.json
      │   vista
      ▼
   data/unity/<edificio>.json          lo que dibuja el visor
```

**Por qué el JSON del medio importa.** En `data/modelo/` un edificio ya
no es "planos 2017_67" ni "eje 3′": es una lista de nodos y elementos en
coordenadas absolutas. A ese nivel los dos hablan el mismo idioma, y
unirlos deja de ser fusionar dos programas y pasa a ser un script que
aplica el calce, renumera los tags y verifica la junta.

**`comun/calcular.py` no sabe de qué edificio se trata**, y ese es todo
el punto: el mismo archivo resuelve el LT2, el tuyo y el conjunto sin
una línea de diferencia. Su motor es `construir_y_resolver()` de tu
`servidor_opensees.py` — la misma función que corre cuando Unity pide un
reanálisis, así que la línea de comandos y el visor no pueden divergir.

Hoy funciona de punta a punta para el LT2:

```bash
python edificios/lt2/armar.py     # geometría -> modelo
python comun/calcular.py lt2      # modelo -> resultados
```

---

## 7. Lo que te toca a vos (y es corto)

Un `edificios/ingenieria/armar.py` que escriba
`data/modelo/ingenieria.json`. **No hace falta tocar `benchmark_3d.py`.**
Tu `export_unity.construir_json()` ya devuelve el diccionario completo,
así que el adaptador es del orden de 30 líneas:

```python
import os, sys
_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_RAIZ, 'comun'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import contrato
import export_unity

completo = export_unity.construir_json()
estructura, vista = contrato.separar(completo)

problemas = contrato.validar(estructura)     # caza cargas huérfanas
if problemas:
    for p in problemas[:10]:
        print('  -', p)
    raise SystemExit(1)

print(contrato.guardar_modelo('ingenieria', estructura))
```

Con eso ya podés correr `python comun/calcular.py ingenieria`, y el
conjunto queda a un paso.

**Esa receta está probada.** La corrí antes de escribirla y anda:

```
360 nodos, 694 elementos (240 columna, 44 muro, 210 viga_x, 200 viga_y),
26 secciones, 5 diafragmas, 4 caso(s)
```

Y el solver genérico reproduce tus números **exactos**, caso por caso:

| caso | equilibrio | error relativo |
|---|---|---|
| G | aplicada 67 067.20 = reacción 67 067.20 kN | 6.0e−09 |
| Q | aplicada 11 272.50 = reacción 11 272.50 kN | 2.7e−08 |
| EX | aplicada 6 523.66 = reacción 6 523.66 kN | 4.6e−08 |
| EY | aplicada 6 523.66 = reacción 6 523.66 kN | 1.5e−08 |

Borré los JSON que generó la prueba, porque ese paso es tuyo: cuando
agregues tu `armar.py`, se regeneran.

> **Un detalle que me costó y te va a servir:** al escribir el chequeo de
> equilibrio genérico sumé todas las filas de `reacciones`, y para EX me
> dio 26 423 kN contra los 6 523 aplicados. El motivo lo tenías
> documentado en tu propio `export_unity.py`: **`nodeReaction` en un nodo
> atado por un diafragma devuelve también la fuerza de esa restricción**,
> que es interna. Pero tampoco se pueden descartar esos nodos enteros:
> tus arranques de muro escalonados son apoyos verticales de verdad y
> aportan 1 504 kN a G.
>
> La separación correcta es **por grado de libertad**: un diafragma
> horizontal ata `ux, uy, rz`, así que en Fx y Fy sólo valen los nodos
> fuera de todo diafragma, y en Fz vale cualquier nodo restringido menos
> el maestro. Está implementado y comentado en `comun/calcular.py`.

`contrato.validar()` revisa justo lo que **rompe en silencio**: una
carga que apunta a un elemento que ya no existe no hace fallar a
OpenSees — avisa por consola y **la descarta**. El análisis corre con
menos peso del que creés y el equilibrio cierra igual, porque lo
descartado nunca entró.

---

## 8. Unity: qué se resolvió y qué te queda pendiente

Los dos habíamos tocado los mismos `.cs`. **Los 7 conflictos se
resolvieron; el proyecto Unity es uno solo y sirve para los tres
edificios.**

Se quedó la versión que es superconjunto: dibuja los muros como placa
orientada, las barras con su sección real `b × h`, los brazos rígidos
como línea fina, y los polígonos tributarios con `tamanos` (un trapecio
de 4 vértices y un triángulo de 3 no se pueden partir en partes
iguales; sin ese campo salían líneas cruzadas).

**Se conservó tu `colorTributaria` y tus toggles de áreas tributarias**,
y el visor **acepta las dos convenciones de muro**:

- tu JSON declara el tamaño en planta en la **sección** → sigue funcionando;
- el del LT2 lo declara en el **elemento** (dos muros pueden compartir
  sección y medir distinto) → se prefiere ese cuando viene.

Igual con la dirección del muro: si el JSON no trae `dir_largo`, el
visor cae a `vecxz`, que es lo que hacía tu versión.

**Lo que te queda pendiente si querés el visor completo para tu
edificio:** que `export_unity.py` emita también `dir_largo` por muro y
los polígonos como `vertices` + `tamanos`. No es urgente — sin eso los
muros se dibujan igual (por la sección) y los polígonos con `vx`/`vy`.
Y cuando conectes el pipeline del punto 7, sale gratis.

---

## 9. Lo que NO cambió

- La regla de oro: **OpenSees calcula, los JSON son la fuente de verdad,
  Unity sólo muestra.** Nada de lógica estructural en C#.
- Ejes: OpenSees Z vertical, Unity Y vertical, conversión centralizada
  en `Ejes.AUnity()`.
- Unidades: m, kN, kPa.
- El cruce de inercias en las vigas horizontales. **No lo "arregles".**
- `eleResponse(tag, 'localForce')`, nunca `eleForce(tag)`.
- Hay que llamar `ops.reactions()` antes de leer reacciones.
- `JsonUtility` no da error si un nombre de campo no calza: deja el
  valor por defecto y la deformada sale plana, en silencio.
- Tus números del edificio de Ingeniería: 360 nodos, 694 elementos,
  G = 67 067 kN, corte basal 6 524 kN. Se verificó que siguen saliendo
  iguales después de mover todo.

Y `PARA_EL_EQUIPO.md` sigue vigente en todo lo demás — este archivo sólo
le agrega el reorden.
