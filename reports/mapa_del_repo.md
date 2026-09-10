# Mapa del repo — hoja para imprimir

**A1P1.0_Grupo_7** · Edificio de Ingeniería UAndes, dos cuerpos (LT2 + antiguo) · OpenSees + Unity

---

## El flujo

```
   PLANOS DXF                GEOMETRÍA               MODELO                RESULTADOS              UNITY
  Planos/*.dxf   ──►  data/geometria/<ed>.json ──► data/modelo/<ed>.json ──► data/resultados/<ed>_<caso>.json ──► data/unity/<ed>.json
                 planos/extraer.py          armar.py            comun/calcular.py           exportar_unity.py
                        │                      │                       │                          │
                  perfiles/*.json        contrato.py          servidor_opensees.py        lanzar_unity.py
                  (lo supuesto)          (el idioma común)     (el motor)                  (copia y abre)
```

Regla de oro: **OpenSees calcula → el JSON es la fuente de verdad → Unity solo muestra.**
`<ed>` = `lt2` · `ingenieria` · `conjunto`. Los dos cuerpos se unen en `data/modelo/`, donde ya hablan igual.

## Tres comandos

```
.\setup.ps1                                              una vez: crea .venv e instala
python comun\verificar_todo.py                           corre las 27 comprobaciones
python comun\lanzar_unity.py app conjunto --pantalla-completa     lo abre en Unity
```

Parámetros del profesor por línea de comandos: `--q 2.5 --cs 0.15 --comb 1.2 1.6 1.0 0.3 --patron manual --fracciones 5 10 20 30 35`

---

## Qué hace cada archivo

### `comun/` — sirve para cualquier edificio

| archivo | hace |
|---|---|
| `rutas.py` | el único que sabe dónde está cada carpeta |
| `contrato.py` | define el modelo neutro; `separar()` sella el área tributaria; `validar()` caza cargas huérfanas; normaliza polígonos |
| `servidor_opensees.py` | construye el modelo en OpenSees y resuelve; servidor Flask para reanálisis desde Unity |
| `calcular.py` | resuelve G, Q, EX, EY → `data/resultados/`; `equilibrio()` separa reacciones por GDL |
| `combinar.py` | superposición R = ΣλR vs corrida explícita, todos los GDL; tolerancia = cota de redondeo |
| `sismo.py` | corte basal, sentido de la deformada, torsión de piso (NCh433), centro de rigidez |
| `capacidad.py` | Fiber Section desde el modelo: M-φ, P-M, Mander desde el estribo, dibujo de fibras |
| `verificar_tributarias.py` | losa aplicada = losa dibujada, q constante por piso |
| `test_contrato_unity.py` | cada clave JSON tiene su campo C# (JsonUtility no avisa) |
| `verificar_todo.py` | corre toda la suite |
| `lanzar_unity.py` | regenera, copia con el nombre que declara la escena, abre |

### `edificios/lt2/` — cuerpo nuevo, planos 2024_22 (Pedro)

| archivo | hace |
|---|---|
| `perfiles/lt2_2024_22.json` | capas, ventana, cargas, sismo, dinteles, longitudinal: **todo lo supuesto, con su razón** |
| `planos/extraer.py` | orquesta la lectura de DXF → `data/geometria/lt2.json` |
| `planos/lectura.py` `ejes.py` `niveles.py` `muros.py` `pilares.py` `vigas.py` `losas.py` `alineacion.py` | cada uno saca una cosa de la lámina y las registra entre sí |
| `planos/enfierradura.py` | estribos de 40 pilares; malla y barras de borde de 31 muros; remisión `VER ELEV. EJE X` |
| `malla.py` | corta vigas en intersecciones reales; brazos rígidos a los muros |
| `panos.py` | paños = caras del grafo de vigas; reparto a 45° (Sutherland–Hodgman) |
| `modelo_lt2.py` | arma OpenSees: secciones, diafragmas, brazos, cargas, sismo por nivel |
| `armar.py` `exportar_unity.py` | etapas 2 y 4 |
| `verificar_lt2.py` | 13 verificaciones: secciones a mano, equilibrio, muros, diafragma, huecos, losa, derivas |
| `tests/` | lectura del DXF; reanálisis con el servidor |

### `edificios/ingenieria/` — cuerpo antiguo, planos 2017_67 (Eduardo)

| archivo | hace |
|---|---|
| `planos_v2.py` | ejes con quiebre de globo, muros por línea y hatch, registro entre láminas |
| `benchmark_3d.py` | el modelo: pórticos, subterráneo, fundación escalonada, voladizos metálicos |
| `enfierradura.py` | armadura de 82 columnas desde la lámina típica |
| `armar.py` `export_unity.py` `verificar_planos.py` `tests/` | etapas 2 y 4; modelo vs DXF a 1 cm; round-trip |

### `edificios/conjunto/` — los dos cuerpos

| archivo | hace |
|---|---|
| `calce.json` | dx, dy, dz medidos sobre ejes compartidos; la junta declarada (5 cm) |
| `armar.py` | une los modelos: calce, renumeración, E/G por cuerpo, **mide** junta y cotas |
| `exportar_unity.py` `verificar_conjunto.py` | polígonos de ambos; cada cuerpo dentro = cuerpo solo, exacto |

### `semana03/` — casos base, superposición, capacidad (Monse)

| archivo | hace |
|---|---|
| `parametros.json` `.py` | q, Cs, patrón en altura, combinaciones; override por CLI |
| `lab_semana03.py <ed>` | Partes A, B y C sobre cualquier edificio, en memoria, delegando en `sismo.py` y `combinar.py` |
| `verificar_rc.py` | fibras vs cálculo a mano (Whitney, β₁, balanceado), cada diferencia explicada |
| `demanda_capacidad.py` | el (P, M) de cualquier columna o muro sobre su curva; `--mphi` a los axiales de su demanda |
| `verificar_viga_partida.py` | refinar una viga partida no cambia la flecha: el nodo no es rótula; la hunde la losa de la perpendicular |
| `exportar_unity.py` + `VisorSemana03.cs` | flechas de carga, deformada sísmica, jaula de armadura |

### `unity/Assets/Scripts/` · raíz

`ModeloEstructural.cs` (datos) · `VisorEstructura.cs` (dibuja) · `AnalizadorEstructural.cs` (servidor) · `EditorEstructura.cs` · `VisorQA.cs` · `VisorSemana03.cs` · `CamaraOrbital.cs`
`README.md` (flujo) · `CLAUDE.md` (reglas y trampas) · `AGENTS.md` (registro de IA) · `GUIA_unity_paso_a_paso.md` · `benchmark/` (S1) · `reports/`

---

## Cinco convenciones que se preguntan

1. **Z vertical en OpenSees, Y en Unity** — `Unity(x, z, y)`.
2. **`Iz` = inercia de gravedad**; el servidor cruza Iy/Iz solo en barras no verticales.
3. **`eleResponse(tag,'localForce')`**, nunca `eleForce` (global).
4. **Un nodo de diafragma reacciona a su restricción**: se separa por GDL o el corte sale al doble.
5. **Lo supuesto se declara en `perfiles/*.json`**, no en código.

## Números de control

LT2: 232 nodos, 378 elementos, G = 34 148.98 kN · Ingeniería: 326 / 559, G = 50 652.2 kN · Conjunto: 558 / 937, G = 84 801.2 kN, junta 0.050 m
Torsión LT2 bajo EY: r = 1.70 (extrema), excentricidad 35 % · P.70x70: Mn(P=0) = 988 kN·m · Benchmark S1: UZ = −0.0635 mm
