# Guía del repositorio — flujo, archivos y comandos

**A1P1.0_Grupo_7** · Edificio de Ingeniería UAndes · OpenSees + Unity
Hoja para imprimir. Todos los comandos de acá están probados y corren.

---

# PARTE 1 — EL FLUJO

```
   PLANOS DXF              GEOMETRÍA                 MODELO                  RESULTADOS                UNITY
  Planos/*.dxf   ──►  data/geometria/<ed>.json ──► data/modelo/<ed>.json ──► data/resultados/<ed>_<caso>.json ──► data/unity/<ed>.json
                  planos/extraer.py          armar.py             comun/calcular.py            exportar_unity.py
                         │                       │                        │                           │
                   perfiles/*.json         contrato.py           servidor_opensees.py         lanzar_unity.py
                   (lo supuesto)           (el idioma común)      (el motor)                   (copia y abre)
```

**Regla de oro:** OpenSees calcula → el JSON es la fuente de verdad → Unity solo muestra.
Nunca lógica de cálculo estructural en C#.

`<ed>` es uno de tres: **`lt2`** (cuerpo nuevo) · **`ingenieria`** (cuerpo antiguo) · **`conjunto`** (los dos unidos).
`<caso>` es uno de cuatro: **G** (peso propio + losa) · **Q** (sobrecarga) · **EX** / **EY** (sismo).

**Por qué cuatro etapas y no un script:** cada JSON se puede mirar y verificar solo. `data/modelo/` es
el punto donde los dos edificios hablan el mismo idioma, y por eso `conjunto/armar.py` los une ahí sin
tener que fusionar dos programas. `comun/calcular.py` no sabe de qué edificio se trata.

---

# PARTE 2 — QUÉ HACE CADA ARCHIVO

## `comun/` — sirve para cualquier edificio

| archivo | qué hace |
|---|---|
| `rutas.py` | El único que sabe dónde está cada carpeta. Encuentra la raíz subiendo hasta la marca del repo. |
| `contrato.py` | Define el modelo neutro. `separar()` sella el área tributaria y los ejes locales en cada elemento; `validar()` caza cargas huérfanas; normaliza los polígonos al formato que lee el C#. |
| `servidor_opensees.py` | El motor: construye el modelo en OpenSees y resuelve. También es el servidor Flask para reanálisis en vivo desde Unity. |
| `calcular.py` | Etapa 3: resuelve G, Q, EX, EY. `equilibrio()` separa reacciones de restricciones **por grado de libertad**. |
| `combinar.py` | Superposición `R = ΣλR` contra una corrida explícita, sobre todos los GDL. La tolerancia es la cota de redondeo, medida. |
| `sismo.py` | Corte basal, sentido de la deformada, torsión de piso (NCh433), centro de rigidez. |
| `capacidad.py` | Fiber Section desde el modelo: M-φ, curva P-M, confinamiento de Mander desde el estribo real. Columna o muro. |
| `verificar_tributarias.py` | La losa que se aplica es la que se dibuja: `q` implícito constante por piso. |
| `test_contrato_unity.py` | Cada clave del JSON tiene su campo en el C#. `JsonUtility` no avisa si falta. |
| `verificar_todo.py` | Corre las 27 comprobaciones y resume. |
| `lanzar_unity.py` | Regenera, copia a `StreamingAssets/` con el nombre que declara la escena, y abre el visor. |

## `edificios/lt2/` — cuerpo nuevo, planos 2024_22

| archivo | qué hace |
|---|---|
| `perfiles/lt2_2024_22.json` | Capas, ventana, cargas, sismo, dinteles, diámetro del longitudinal: **todo lo supuesto, con su razón escrita**. |
| `planos/extraer.py` | Orquesta la lectura de los DXF → `data/geometria/lt2.json` + auditoría. |
| `planos/lectura.py` | Abre una lámina, explota los bloques y XREFs, deja todo en metros. |
| `planos/ejes.py` · `niveles.py` · `muros.py` · `pilares.py` · `vigas.py` · `losas.py` | Cada uno saca una cosa de la lámina. |
| `planos/alineacion.py` | Registra plantas entre sí por los ejes que comparten. |
| `planos/enfierradura.py` | El fierro desde las elevaciones: estribos de 40 pilares, malla y barras de borde de 31 muros. |
| `planos/perfil.py` · `inventario.py` | Lee el perfil; inventaría capas y láminas. |
| `malla.py` | Corta las vigas en sus intersecciones reales; engancha muros con brazos rígidos. |
| `panos.py` | Paños = caras del grafo de vigas; reparto a 45° (Sutherland–Hodgman). |
| `modelo_lt2.py` | Arma OpenSees: secciones, diafragmas, brazos, las tres vías de carga, sismo por nivel. |
| `armar.py` · `exportar_unity.py` | Etapas 2 y 4. |
| `verificar_lt2.py` | 59 comprobaciones del modelo. |
| `tests/` | Lectura del DXF; reanálisis con el servidor. |

## `edificios/ingenieria/` — cuerpo antiguo, planos 2017_67

| archivo | qué hace |
|---|---|
| `planos_v2.py` | Ejes con quiebre de globo, muros por línea y por hatch, registro entre láminas. |
| `benchmark_3d.py` | El modelo: pórticos, subterráneo como zona, fundación escalonada, voladizos metálicos. |
| `enfierradura.py` | Armadura de las 82 columnas, trazable a la lámina típica. |
| `armar.py` · `export_unity.py` · `verificar_planos.py` · `tests/` | Etapas 2 y 4; modelo vs DXF a 1 cm; round-trip. |

## `edificios/conjunto/` — los dos cuerpos

| archivo | qué hace |
|---|---|
| `calce.json` | `dx`, `dy`, `dz` medidos sobre ejes compartidos; la junta declarada (5 cm). |
| `armar.py` | Une los modelos: calce, renumeración, **E/G por cuerpo**, y mide junta y cotas. |
| `exportar_unity.py` · `verificar_conjunto.py` | Polígonos de ambos; cada cuerpo dentro = cuerpo solo, exacto. |

## `semana03/` — casos base, superposición, capacidad

| archivo | qué hace |
|---|---|
| `parametros.json` · `parametros.py` | q, Cs, patrón en altura, combinaciones. Con override por línea de comandos. |
| `lab_semana03.py <ed>` | Partes A, B y C sobre cualquier edificio: arma Q, EX y EY en memoria y delega en `sismo.py` y `combinar.py`. |
| `verificar_rc.py <ed> <elem>` | Fibras contra cálculo a mano (Whitney, β₁, balanceado). Cada diferencia explicada. |
| `demanda_capacidad.py <ed> <elem>` | El (P, M) de cualquier columna o muro sobre su curva. |
| `verificar_viga_partida.py` | Refinar una viga partida no cambia la flecha: el nodo no es rótula. |
| `exportar_unity.py` + `VisorSemana03.cs` | Flechas de carga, deformada sísmica y jaula de armadura en Unity. |
| `reports/semana03.md` | El informe del avance. |

## `unity/Assets/Scripts/` y raíz

`ModeloEstructural.cs` (las clases de datos) · `VisorEstructura.cs` (dibuja) · `AnalizadorEstructural.cs`
(habla con el servidor) · `EditorEstructura.cs` · `VisorQA.cs` (toggles) · `VisorSemana03.cs` · `CamaraOrbital.cs`
`README.md` (mapa) · `CLAUDE.md` (reglas y trampas) · `AGENTS.md` (registro de IA) · `benchmark/` (Semana 1)

---

# PARTE 3 — CÓMO CORRER TODO

## 3.1 Preparar el entorno (una sola vez)

```powershell
cd "...\P1\A1P1.0_Grupo_7"
.\setup.ps1
```

Crea `.venv`, instala `openseespy`, `ezdxf`, `matplotlib`, `flask` y avisa si falta Unity.
Si PowerShell bloquea el script, antes: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`

**Dos formas de usar el entorno.** La segunda es la recomendada: no hay que acordarse de activar nada.

```powershell
.\.venv\Scripts\Activate.ps1        # activarlo; el prompt queda con (.venv)
python comun\verificar_todo.py      # ...y ya se usa "python" a secas
deactivate                          # salir

.\.venv\Scripts\python.exe comun\verificar_todo.py     # sin activar nada
```

> En esta guía se escribe `python` por brevedad. Si no activaste el entorno, poné
> `.\.venv\Scripts\python.exe` en su lugar.

## 3.2 ¿Está todo bien? — el comando de siempre

```powershell
python comun\verificar_todo.py            # las 27 comprobaciones (~25 s)
python comun\verificar_todo.py --rapido   # sin las lentas
python comun\verificar_todo.py --solo sismo combinar
```

**Si dice `27 de 27 EN OK`, el repo está como se entrega.** Correlo antes de cada `push`.

## 3.3 Regenerar el modelo desde cero

Solo hace falta si tocaste los planos, el perfil o el código del modelo.

```powershell
python edificios\lt2\armar.py                    # geometría -> modelo
python comun\calcular.py lt2                     # modelo -> resultados (4 casos)
python edificios\lt2\exportar_unity.py           # -> data/unity/lt2.json

python edificios\ingenieria\armar.py             # lo mismo para el otro cuerpo
python comun\calcular.py ingenieria
python edificios\ingenieria\export_unity.py

python edificios\conjunto\armar.py               # une los dos (después de los dos anteriores)
python comun\calcular.py conjunto
python edificios\conjunto\exportar_unity.py
```

Volver a leer los DXF (lento, necesita la carpeta `Planos/`):

```powershell
python edificios\lt2\planos\extraer.py "..\Planos\LT2_CAL_dxf" --perfil lt2_2024_22 --salida data\geometria\lt2.json
```

## 3.4 Abrir el visualizador 3D

```powershell
python comun\lanzar_unity.py app conjunto --pantalla-completa
python comun\lanzar_unity.py app lt2
python comun\lanzar_unity.py app ingenieria
```

Eso copia el JSON a `StreamingAssets/` **con el nombre que la escena declara** y abre la app.
La primera vez compila (varios minutos); después arranca en segundos.

| modo | para qué |
|---|---|
| `app <ed>` | abrir el visor. **Es el de la demostración.** |
| `editor` | abrir el proyecto en Unity, para trabajar en el visor. Hay que apretar Play a mano. |
| `build --forzar` | recompilar la app tras cambiar un `.cs` |
| `servidor` | levantar el servidor de reanálisis en primer plano |

Atajo del LT2 (hace exportar + abrir de una):

```powershell
.\ver.ps1                  # exporta el LT2 y abre el visor
.\ver.ps1 -Servidor        # además levanta el servidor de reanálisis
.\ver.ps1 -Recompilar      # recompila la app antes de abrir
.\ver.ps1 -SoloExportar    # solo regenera el JSON, no abre nada
```

**Reanálisis en vivo** (editar en Unity y recalcular): en otra terminal,

```powershell
python comun\servidor_opensees.py            # solo esta máquina (127.0.0.1:5000)
python comun\servidor_opensees.py --lan      # abierto a la red local, para el celular (AR)
```

## 3.5 Los diagramas de capacidad

Todos los gráficos salen a **`semana03/resultados/`**.

**Ver qué elementos tienen armadura y elegir uno:**

```powershell
python semana03\demanda_capacidad.py lt2 --lista
python semana03\demanda_capacidad.py ingenieria --lista
```

**El diagrama P-M con el punto de demanda encima** — es *el* gráfico de la defensa:

```powershell
python semana03\demanda_capacidad.py lt2 1 --grafico          # columna P.70x70
python semana03\demanda_capacidad.py lt2 9 --grafico          # muro M 0.25x7.95
python semana03\demanda_capacidad.py ingenieria 18 --grafico
```
→ `pm_<ed>_<elem>.png`

**Con una combinación dictada por el profesor** (λG λQ λEX λEY):

```powershell
python semana03\demanda_capacidad.py lt2 1 --comb 1.2 1.6 1.0 0.3 --grafico
```

**Todos los elementos de una** (tabla con la utilización de cada uno):

```powershell
python semana03\demanda_capacidad.py lt2 --todas --comb 1.2 1.6 1.0 0.3
python semana03\demanda_capacidad.py ingenieria --todas
```

**La sección: discretización, M-φ y P-M**

```powershell
python comun\capacidad.py lt2 1                    # resumen y M-φ a P=0
python comun\capacidad.py lt2 1 --pm               # + la curva P-M, interpretada
python comun\capacidad.py lt2 1 --mphi             # + M-φ a varios axiales
python comun\capacidad.py lt2 1 --dibujo           # + la discretización en fibras
python comun\capacidad.py lt2 1 --sensibilidad     # ¿alcanzan 20 fibras?
python comun\capacidad.py ingenieria 18 --pm --mphi --dibujo    # todo junto
```
→ `fibras_<ed>_<elem>.png` · `mphi_<ed>_<elem>.png` · `pm_<ed>_<elem>.png`

**M-φ a los axiales que le pone su propia demanda:**

```powershell
python semana03\demanda_capacidad.py ingenieria 18 --mphi
```
→ `mphi_<ed>_<elem>_demanda.png`

**Las fibras contra el cálculo a mano** (Whitney, β₁, punto balanceado):

```powershell
python semana03\verificar_rc.py lt2 1        # una columna
python semana03\verificar_rc.py lt2 9        # un muro
python semana03\verificar_rc.py lt2          # los dos, resumido
```

## 3.6 El laboratorio de la Semana 3 (Partes A, B, C)

```powershell
python semana03\lab_semana03.py                  # edificio de Ingeniería
python semana03\lab_semana03.py lt2
python semana03\lab_semana03.py conjunto
```

**Con los parámetros que dicte el profesor** — no hay que editar ningún archivo:

| bandera | qué cambia | ejemplo |
|---|---|---|
| `--q` | sobrecarga de uso, kN/m² | `--q 3` |
| `--cs` | coeficiente sísmico basal | `--cs 0.20` |
| `--fq` | fracción de Q en el peso sísmico | `--fq 0.25` |
| `--patron` | `potencia` o `manual` | `--patron manual` |
| `--k` | exponente del patrón (0 uniforme, 1 triangular, 2 tope NCh433) | `--k 2` |
| `--fracciones` | reparto manual, de abajo hacia arriba | `--fracciones 5 10 20 30 35` |
| `--comb` | los cuatro factores λG λQ λEX λEY | `--comb 1.2 1.6 1.0 0.3` |
| `--combinacion` | una de las declaradas por nombre | `--combinacion 1.2G+1.6Q` |

```powershell
python semana03\lab_semana03.py ingenieria --cs 0.20 --k 2
python semana03\lab_semana03.py lt2 --patron manual --fracciones 5 10 20 30 35
python semana03\parametros.py --q 3 --comb 1.2 1.6 0 0     # solo muestra qué quedaría
```

## 3.7 Verificaciones sueltas

```powershell
python comun\sismo.py lt2                      # los dos casos laterales
python comun\sismo.py lt2 EY --detalle         # cuánto del borde es giro
python comun\combinar.py lt2                   # las 5 combinaciones declaradas
python comun\combinar.py conjunto --comb 1.2 1.6 1.0 0.3
python comun\verificar_tributarias.py          # la losa, los 3 edificios
python edificios\lt2\verificar_lt2.py          # las 59 del LT2
python edificios\conjunto\verificar_conjunto.py
python comun\test_contrato_unity.py lt2        # el contrato con el C#
python semana03\verificar_viga_partida.py ingenieria 373   # la viga que "se hunde"
python semana03\verificar_viga_partida.py lt2              # sin nodo, toma el primero
```

---

# PARTE 4 — LO QUE HAY QUE SABER EXPLICAR

## Cinco convenciones que no se rompen

1. **Z vertical en OpenSees, Y en Unity** — `Unity(x, z, y)`. Si el edificio se ve acostado, es esto.
2. **`Iz` es la inercia de gravedad**; el servidor cruza `Iy`/`Iz` solo en barras **no** verticales.
3. **`eleResponse(tag,'localForce')`**, nunca `eleForce` (que devuelve ejes globales).
4. **Un nodo de diafragma reacciona también a su restricción**, que es interna: se separa por grado de libertad o el corte basal sale al doble.
5. **Lo supuesto se declara en `perfiles/*.json`**, con su razón, no escrito en el código.

## Números de control

| | |
|---|---|
| LT2 | 232 nodos, 378 elementos, G = 34 148.98 kN |
| Ingeniería | 326 nodos, 559 elementos, G = 50 652.2 kN |
| Conjunto | 558 / 937, G = 84 801.2 kN = **la suma**; junta 0.050 m cara a cara |
| Torsión LT2 bajo EY | cociente 1.70 — extrema (NCh433 > 1.4); excentricidad 35 % del ancho |
| Columna P.70x70 | Mn(P=0) = 988 kN·m; tracción pura fibras = a mano, exacto |
| Benchmark Semana 1 | UZ techo = −0.0635 mm (SAP2000: −0.06375, 0.4 %) |

## Si algo se ve raro en el visor

| se ve | es |
|---|---|
| Una viga hundida en el medio | la escala gráfica ×300. 6.55 mm sobre 10 m se dibujan como 1.96 m. Bajá la escala con el slider. |
| El edificio acostado | el swap de ejes Z↔Y. |
| La deformada plana | un campo del C# que no calza con el JSON: `python comun\test_contrato_unity.py <ed>` |
| Datos viejos | no regeneraste: `python comun\lanzar_unity.py app <ed>` lo hace todo. |
| Huecos blancos donde debería haber losa | `python comun\verificar_tributarias.py` |

## Reparto del grupo

Pedro — LT2 y `comun/` · Eduardo — edificio de Ingeniería y visor · Monse — Semana 3
Una carpeta = un dueño. `comun/` y `unity/` son compartidos: se avisa antes de tocarlos.
