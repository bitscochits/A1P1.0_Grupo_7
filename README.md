# Laboratorio Estructural Digital — Grupo 7

Modelo estructural del **Edificio de Ingeniería de la UAndes**, hecho
desde sus planos, resuelto con OpenSees, verificado numéricamente y
visualizado en Unity. Curso *Métodos Computacionales en Obras Civiles*,
2026-02.

El edificio son **dos cuerpos** construidos en dos etapas y separados por
una junta de dilatación:

| cuerpo | planos | carpeta | quién |
|---|---|---|---|
| Ingeniería (antiguo) | `2017_67` | `edificios/ingenieria/` | Eduardo |
| LT2 (nuevo) | `2024_22` | `edificios/lt2/` | Pedro |
| los dos unidos | `calce.json` | `edificios/conjunto/` | común |

Semana 3 (`semana03/`): Monse.

---

## 1. El flujo, en una línea

```
planos DXF → geometría → modelo → resultados → Unity
                  ↓         ↓          ↓
             perfiles/   contrato   verificaciones
```

Cuatro etapas, cada una un JSON en `data/`. **OpenSees calcula, el JSON
es la fuente de verdad, Unity solo muestra.**

```
edificios/<ed>/planos/extraer.py   →  data/geometria/<ed>.json    lo que dice el plano
edificios/<ed>/armar.py            →  data/modelo/<ed>.json       el contrato neutro
comun/calcular.py <ed>             →  data/resultados/<ed>_<caso>.json
edificios/<ed>/exportar_unity.py   →  data/unity/<ed>.json        lo que dibuja Unity
```

`<ed>` es `lt2`, `ingenieria` o `conjunto`. Los dos edificios se unen en
`data/modelo/`, donde ya hablan el mismo idioma.

## 2. Cómo correrlo

```powershell
.\setup.ps1                                  # una vez: crea .venv e instala
python comun\verificar_todo.py               # ¿está todo bien?  (27 comprobaciones)
python comun\lanzar_unity.py app conjunto --pantalla-completa   # verlo
```

Cada script se puede correr solo y explica qué hace en su cabecera.
Los parámetros que dicta el profesor van por línea de comandos:

```powershell
python comun\combinar.py lt2 --q 2.5 --cs 0.15 --comb 1.2 1.6 1.0 0.3
python semana03\lab_semana03.py --patron manual --fracciones 5 10 20 30 35
python semana03\demanda_capacidad.py lt2 9 --grafico     # cualquier columna o muro
```

## 3. Mapa del repo — qué hace cada archivo

> Versión de una hoja, para imprimir: `reports/mapa_del_repo.md`.

### `comun/` — lo que sirve para cualquier edificio

| archivo | qué hace |
|---|---|
| `rutas.py` | El único que sabe dónde está cada carpeta. Encuentra la raíz subiendo hasta la marca del repo. |
| `contrato.py` | Define el modelo neutro (`data/modelo/`): qué es estructura y qué es vista, `validar()` caza cargas huérfanas, `separar()` sella el área tributaria en cada elemento. |
| `servidor_opensees.py` | El motor: construye el modelo en OpenSees y resuelve los casos. También es el servidor Flask para reanálisis desde Unity. |
| `calcular.py` | Etapa 3: lee `data/modelo/`, resuelve G, Q, EX, EY y escribe `data/resultados/`. `equilibrio()` separa reacciones de restricciones **por grado de libertad**. |
| `combinar.py` | Superposición `R = ΣλR` y su prueba contra una corrida explícita, sobre todos los GDL. La tolerancia es la **cota de redondeo** del servidor, medida. |
| `sismo.py` | Un caso lateral: carga aplicada, corte basal, sentido de la deformada, torsión de piso (cociente NCh433) y centro de rigidez. |
| `capacidad.py` | Fiber Section desde el modelo: M-φ, curva P-M nominal (ε_c = 0.003) y máxima, confinamiento de Mander desde el estribo real, sensibilidad, dibujo de la discretización. Columna o muro. |
| `verificar_tributarias.py` | La losa que se aplica es la que se dibuja: área sellada = polígonos = carga, con el q implícito constante por piso. |
| `test_contrato_unity.py <ed>` | Cada clave del JSON tiene su campo en el C#. `JsonUtility` no avisa si falta. |
| `verificar_todo.py` | Corre toda la suite y resume. |
| `lanzar_unity.py app <ed>` | Regenera, copia a `StreamingAssets/` con el nombre **que la escena declara** y abre el visor. |

### `edificios/lt2/` — el LT2, desde sus planos `2024_22`

| archivo | qué hace |
|---|---|
| `perfiles/lt2_2024_22.json` | Todo lo específico del edificio y todo lo **supuesto**, declarado con su razón: capas, ventana, cargas, sismo, dinteles, diámetro del longitudinal. |
| `planos/extraer.py` | Orquesta la lectura de los DXF y escribe `data/geometria/lt2.json` + una auditoría. |
| `planos/lectura.py` | Abre una lámina, explota los bloques, deja todo en metros. |
| `planos/ejes.py` `niveles.py` `muros.py` `pilares.py` `vigas.py` `losas.py` | Cada uno saca una cosa de la lámina. `muros.py` une los muros partidos por un cruce. |
| `planos/alineacion.py` | Registra plantas entre sí por los ejes que comparten; alinea fachadas casi colineales. |
| `planos/enfierradura.py` | El fierro desde las elevaciones: estribos y trabas de los 40 pilares, malla y barras de borde de los muros, con la referencia cruzada `VER ELEV. EJE X`. |
| `planos/perfil.py` `inventario.py` | Lee el perfil; inventaría capas y láminas. |
| `malla.py` | Corta las vigas en sus intersecciones reales y engancha los muros con brazos rígidos. |
| `panos.py` | Encuentra los paños como caras del grafo de vigas y reparte la losa a 45° (Sutherland–Hodgman). |
| `modelo_lt2.py` | Arma el modelo en OpenSees: secciones, diafragmas, brazos, las tres vías de carga, sismo por nivel. |
| `armar.py` | Etapa 2: geometría → `data/modelo/lt2.json`, pegando la enfierradura a cada elemento. |
| `exportar_unity.py` | Etapa 4: `data/unity/lt2.json` con ejes locales, polígonos tributarios y los cuatro casos. |
| `verificar_lt2.py` | 13 verificaciones del modelo: secciones a mano, equilibrio, orientación de muros, linealidad, diafragma, brazos, huecos, losa piso a piso, casos, derivas NCh433. |
| `tests/` | `test_planos.py` (la lectura del DXF), `test_reanalisis.py` (el servidor con el LT2). |

### `edificios/ingenieria/` — el cuerpo antiguo, planos `2017_67`

| archivo | qué hace |
|---|---|
| `planos_v2.py` | Lee los DXF: ejes con quiebre de globo, muros por línea y por hatch, registro entre láminas. |
| `benchmark_3d.py` | El modelo: grilla de pórticos, subterráneo como zona, fundación escalonada, voladizos metálicos, muros como columna ancha. |
| `enfierradura.py` | Armadura de las 82 columnas, trazable a la lámina típica. |
| `armar.py` `export_unity.py` | Etapas 2 y 4 de este edificio. |
| `verificar_planos.py` | El modelo contra los DXF, a 1 cm. |
| `tests/test_contrato_unity.py` | Round-trip: el JSON exportado da lo mismo que el modelo en memoria. |

### `edificios/conjunto/` — los dos cuerpos

| archivo | qué hace |
|---|---|
| `calce.json` | La transformación entre los dos planos (`dx`, `dy`, `dz`), medida sobre ejes compartidos, y la junta declarada. |
| `armar.py` | Une los dos `data/modelo/`: aplica el calce, renumera, sella `E`/`G` por cuerpo, y **mide** que la junta sea la declarada y las cotas coincidan. |
| `exportar_unity.py` | Junta los polígonos de los dos cuerpos con el mismo calce. |
| `verificar_conjunto.py` | Con la junta libre, cada cuerpo dentro del conjunto debe dar **exactamente** lo mismo que solo. |

### `semana03/` — casos base, superposición y capacidad

| archivo | qué hace |
|---|---|
| `parametros.json` `parametros.py` | Lo que define el profesor: q, coeficiente sísmico, patrón en altura, combinaciones. Con override por CLI. |
| `lab_semana03.py <ed>` | Partes A, B y C sobre cualquier edificio: arma Q, EX y EY en memoria con los parámetros del profesor y delega en `sismo.py` y `combinar.py`. |
| `verificar_rc.py <ed> <elem>` | Fibras contra cálculo a mano (Whitney, β₁, balanceado). Cada diferencia explicada. |
| `demanda_capacidad.py <ed> <elem>` | El (P, M) de cualquier columna o muro sobre su curva; `--todas` para todos; `--mphi` las M-φ a los axiales de su demanda. |
| `verificar_viga_partida.py <ed> <nodo>` | Refina una viga partida en 2, 4, 8 y 16 tramos y muestra que la flecha no cambia: el nodo compartido no es una rótula, y lo que la hunde es la losa que trae la viga perpendicular. |
| `exportar_unity.py` + `unity/.../VisorSemana03.cs` | Flechas de carga, deformada sísmica y jaula de armadura en Unity, sobre la sección de `comun/capacidad.py`. |
| `reports/semana03.md` | El informe del avance, con todos los números salidos de correr los scripts. |
| `GUIA_SEMANA3.md` | Guía de estudio para la defensa. |

### `unity/Assets/Scripts/`

`ModeloEstructural.cs` (las clases de datos, fuente de verdad del
contrato) · `VisorEstructura.cs` (dibuja) · `AnalizadorEstructural.cs`
(habla con el servidor) · `EditorEstructura.cs` · `VisorQA.cs` (toggles)
· `VisorSemana03.cs` · `CamaraOrbital.cs`.

### Raíz

`CLAUDE.md` (reglas y trampas para agentes) · `AGENTS.md` (registro de
IA que pide el curso) · `GUIA_unity_paso_a_paso.md` · `benchmark/`
(Semana 1) · `reports/` (informes) · `setup.ps1` · `test_servidor.py`.

## 4. Convenciones que no se rompen

Están en `CLAUDE.md`, sección 4. Las cinco que más se preguntan:

1. **Z vertical en OpenSees, Y en Unity**: `Unity(x, z, y)`.
2. **`Iz` es la inercia de gravedad**; el servidor cruza `Iy`/`Iz` solo en barras no verticales.
3. **`eleResponse(tag,'localForce')`**, nunca `eleForce`.
4. **Un nodo de diafragma reacciona también a su restricción**: se separa por GDL o el corte basal sale al doble.
5. **Lo supuesto se declara en `perfiles/*.json`**, no en el código.

## 5. Números de control

| | |
|---|---|
| LT2 | 232 nodos, 378 elementos, G = 34 148.98 kN |
| Ingeniería | 326 nodos, 559 elementos, G = 50 652.2 kN |
| Conjunto | 558 / 937, G = 84 801.2 kN = la suma; junta 0.050 m cara a cara |
| Torsión LT2 bajo EY | cociente 1.70 — extrema (NCh433 > 1.4); excentricidad 35 % del ancho |
| Columna P.70x70 | Mn(P=0) = 988 kN·m; tracción pura fibras = a mano exacto |
| Benchmark S1 | UZ techo = −0.0635 mm (SAP2000: −0.06375) |
