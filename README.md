# Laboratorio Estructural Digital — Grupo 7

Modelo estructural de los dos cuerpos del Edificio de Ingeniería UAndes,
armado desde sus planos de cálculo, resuelto con OpenSeesPy y visualizado
en Unity.

```
OpenSees (Python)  ──►  archivos JSON  ──►  Unity  ──►  AR
    CALCULA            fuente de verdad     MUESTRA
```

**Nunca metas lógica de cálculo estructural en C#.** Si hay que calcular
algo, va en Python y viaja por JSON.

---

## Los tres edificios

El repositorio está partido por **edificio**, y cada carpeta tiene un
dueño. Es lo que permite que dos personas trabajen a la vez sin pisarse.

| carpeta | qué es | planos |
|---|---|---|
| `edificios/ingenieria/` | el cuerpo antiguo, "ETAPA ANTERIOR" | `2017_67` |
| `edificios/lt2/` | el cuerpo nuevo | `2024_22` |
| `edificios/conjunto/` | los dos unidos por la junta de dilatación | — |

Los dos son **el mismo edificio en dos etapas**: comparten las seis
cotas de piso (−7.97 a +11.83) y la altura de 3.96 m, y los separa la
junta de dilatación en `x = 42.75`. El conjunto todavía no está armado:
lo que falta y cómo hacerlo está en
[`edificios/conjunto/README.md`](edificios/conjunto/README.md).

---

## El pipeline

Cuatro etapas, y **el archivo entre dos etapas es el contrato**. Si algo
sale mal, se puede abrir el JSON del medio y ver en cuál de las cuatro
está el error.

```
   planos DXF
      │   ingesta            propia de cada edificio
      ▼
   data/geometria/<edificio>.json      lo que DICE el plano
      │   armado             propia de cada edificio
      ▼
   data/modelo/<edificio>.json         listo para calcular  ◄── el contrato neutro
      │   cálculo            comun/calcular.py, uno solo para todos
      ▼
   data/resultados/<edificio>_<caso>.json
      │   vista
      ▼
   data/unity/<edificio>.json          lo que dibuja el visor
```

**La etapa del medio es la importante.** En `data/modelo/` un edificio
ya no es "planos 2024_22" ni "eje A′": es una lista de nodos y elementos
en coordenadas absolutas. Ahí es donde los dos edificios hablan el mismo
idioma, y donde se van a unir.

`comun/calcular.py` **no sabe de qué edificio se trata**, y ese es todo
el punto: el mismo archivo resuelve el LT2, el de Ingeniería y el
conjunto sin una línea de diferencia. Su motor es la misma función que
usa el servidor cuando Unity pide un reanálisis, así que la línea de
comandos y el visor no pueden dar resultados distintos.

---

## Cómo correrlo

### Preparar el entorno (una vez)

```powershell
.\setup.ps1
```

### El LT2, de punta a punta

```powershell
python edificios\lt2\armar.py            # geometría -> modelo
python comun\calcular.py lt2             # modelo -> resultados, los 4 casos
python edificios\lt2\exportar_unity.py   # -> data/unity/lt2.json
```

**Los cuatro casos de carga**

| | de dónde sale | total |
|---|---|---|
| **G** | peso propio + losa + peso muerto del plano de cargas | 34 011.06 kN |
| **Q** | sobrecarga del plano (500 kgf/m², 300 en el techo), por las mismas áreas tributarias a 45° | 11 206.97 kN |
| **EX** | sismo pseudoestático, V = 0.10 × peso sísmico | 3 616.53 kN |
| **EY** | ídem, en la otra dirección | 3 616.53 kN |

G y Q salen del plano de cargas. **El sismo no**: el coeficiente basal,
el factor de sobrecarga y el exponente de reparto son supuestos, y por
eso están declarados en `edificios/lt2/perfiles/lt2_2024_22.json` y no
escritos en el código. No es un cálculo NCh433 completo — falta el
espectro, el factor R, la zona y el tipo de suelo.

El corte basal se reparte en altura como `F_k = V·W_k·h_k / Σ(W·h)` y se
aplica en el **nodo maestro** de cada diafragma, que está en el centro
del piso: aplicarlo en una esquina metería una excentricidad que no
existe. `h` se mide **desde la base**, no como cota absoluta — la base de
este edificio está en −7.97, y usar la cota daría `h` negativo en el
subterráneo, con esos pisos empujando al revés.

Derivas de entrepiso bajo sismo, contra el límite de NCh433 5.9.2
(0.002 de la altura, medida en el centro de masa):

| | peor deriva | dónde | límite |
|---|---|---|---|
| EX | 1/979 | +3.91 | 1/500 |
| EY | 1/1922 | +7.87 | 1/500 |

El edificio es notoriamente más rígido en Y que en X (8.35 mm contra
16.87 mm de desplazamiento de techo), que es lo que corresponde con los
muros del núcleo orientados como están.

### El visor, en un solo comando

```powershell
.\ver.ps1
```

Exporta, compila si hace falta y abre la app. `-SoloExportar` para
quedarse en el JSON; `-Recompilar` para forzar el build.

### El edificio de Ingeniería

```powershell
python edificios\ingenieria\benchmark_3d.py   # modelo + 4 casos + equilibrio
python edificios\ingenieria\export_unity.py   # -> data/unity/ingenieria.json
```

### El servidor (dejarlo abierto para editar desde Unity)

```powershell
python comun\servidor_opensees.py
```

---

## Las verificaciones

Correr **después de cualquier cambio al modelo**. Todas avisan si algo
se rompió.

| comando | qué revisa |
|---|---|
| `python edificios\lt2\verificar_lt2.py` | 36 checks del LT2: equilibrio, diafragmas, áreas tributarias, rótulos de losa |
| `python edificios\lt2\test_planos.py` | 51 checks del ingestor de DXF |
| `python edificios\lt2\tests\test_contrato_unity.py` | los campos del C# contra el JSON |
| `python edificios\lt2\tests\test_reanalisis.py` | ida y vuelta por el servidor |
| `python edificios\ingenieria\verificar_planos.py` | el modelo contra los DXF (ejes y muros) |
| `python edificios\ingenieria\test_contrato_unity.py` | ídem, para su JSON |
| `python benchmark\benchmark_distribuida.py` | el benchmark de Semana 1 sigue intacto |
| `python benchmark\test_areas_tributarias.py` | conservación y geometría del reparto |
| `python test_servidor.py` | multi-caso, diafragmas, apoyos |

---

## Estructura de carpetas

```
edificios/
  ingenieria/   benchmark_3d.py, export_unity.py, verificar_planos.py
  lt2/          planos/ (ingestor DXF), malla.py, panos.py, modelo_lt2.py,
                armar.py, exportar_unity.py, perfiles/, tests/
  conjunto/     el diseño de la unión (todavía sin armar)

comun/          lo que comparten los tres
  rutas.py             dónde está cada cosa: un solo archivo lo sabe
  contrato.py          qué es un "modelo": qué es estructura y qué es dibujo
  calcular.py          la etapa de cálculo, genérica
  servidor_opensees.py el servidor Flask que atiende a Unity
  lanzar_unity.py      compila y abre el visor

benchmark/      el benchmark de la Semana 1, validado contra SAP2000
                (número de oro: UZ techo bajo G = −0.06348 mm)

data/
  geometria/    lo que dice el plano
  modelo/       listo para calcular
  resultados/   lo que OpenSees calculó
  unity/        lo que dibuja el visor

unity/          el proyecto Unity: un solo visor para los tres
reports/        los informes semanales
```

### Por qué `comun/rutas.py`

Antes cada script calculaba la raíz contando `os.path.dirname`. Eso
funciona hasta que el archivo cambia de carpeta — y entonces apunta un
nivel más arriba **sin fallar**: escribe el JSON en el lugar equivocado,
o lee uno viejo que quedó en la ubicación anterior. El síntoma aparece
mucho después, en Unity, como un modelo que "no se actualiza".

Ahora la raíz se busca subiendo hasta encontrar la marca del
repositorio, así que no depende de la profundidad del que pregunta.
Corré `python comun\rutas.py` para ver qué resolvió.

---

## Reparto del grupo

- **Pedro** — el LT2 (`edificios/lt2/`) y el ingestor de planos.
- **Su compañero** — el edificio de Ingeniería (`edificios/ingenieria/`).
- **Los dos** — `comun/`, `unity/` y el conjunto: acordar antes de tocar.

Una carpeta, un dueño. Si necesitás algo de la otra mitad, se pide por
el JSON de `data/modelo/`, no importando su código.

---

## Convenciones que no se rompen

**Ejes.** OpenSees usa Z vertical (convención de ingeniería); Unity usa
Y vertical (convención de videojuego). La conversión es
`Unity(x, z_opensees, y_opensees)` y vive **en un solo lugar**:
`Ejes.AUnity()`. No la dupliques.

**Unidades.** Todo en m, kN, kPa.

**El cruce de inercias.** En la llamada `element` de OpenSees las
inercias van cruzadas para los elementos horizontales, porque con
`vecxz=(0,0,1)` el eje local *y* queda vertical. Está comentado en el
código. No lo "arregles".

**Esfuerzos internos.** Siempre `eleResponse(tag, 'localForce')`, nunca
`eleForce(tag)`: el segundo devuelve ejes globales, y para una viga que
corre en Y el momento de gravedad aparecería en la casilla de torsión.

**Reacciones.** Hay que llamar `ops.reactions()` antes de leerlas, si no
salen todas cero.

**El esquema del JSON.** Unity depende de él campo por campo, y
`JsonUtility` **no da error** si un nombre no calza: deja el campo en su
valor por defecto y la deformada sale plana, en silencio. Por eso están
los `test_contrato_unity.py`.

**Borrar elementos.** Si borrás una barra y queda su carga distribuida,
OpenSees avisa por consola y **descarta la carga**. El análisis
"funciona" con menos peso del que creés, y el equilibrio cierra igual
porque la carga descartada nunca entró. `contrato.validar()` caza
exactamente eso.
