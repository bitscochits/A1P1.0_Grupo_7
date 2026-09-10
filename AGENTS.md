# AGENTS.md — Registro de uso de agentes de IA

> Documenta cómo el grupo usa agentes de IA en el proyecto. Es parte de
> la evaluación del curso: lo que importa no es que la IA haya escrito
> código, sino **qué propuso, qué se revisó y qué se corrigió**.

---

## Agentes en uso

| Agente | Para qué | Quién |
|---|---|---|
| Claude Code (Opus / Fable) | modelado desde planos, verificaciones, capacidad, superposición, consolidación del repo | Pedro |
| Claude Code | edificio de Ingeniería, Parte D y visor de Semana 3 | Eduardo |
| Claude Code | scripts de Semana 3, guía de estudio | Monse |

## Criterios de aceptación

1. **Verificación numérica** contra un valor conocido o una propiedad
   que tiene que cumplirse (equilibrio, simetría, conservación).
2. **Equilibrio**: carga aplicada = reacciones, error relativo < 1e-6,
   separado por grado de libertad en los nodos de diafragma.
3. **No romper la arquitectura**: OpenSees calcula, Unity muestra.
4. **Código entendible**: cualquier integrante debe poder explicarlo.
5. **Sin cambios al contrato JSON** sin acuerdo del grupo.
6. **Lo supuesto se declara** en `perfiles/*.json`, con su razón.

## Ciclo de trabajo

```
Issue → Plan → Build → Test (python comun/verificar_todo.py) → Review → Merge
```

Un buen encargo tiene criterio de aceptación: *"leer el fierro de los
40 pilares del LT2; cada uno debe emparejar con un solo elemento del
modelo y el conteo debe cerrar con los rótulos del plano"*. Uno malo:
*"haz la enfierradura"*.

---

## Registro semanal

### Semana 1 — benchmark
- **Tarea:** marco 3D de prueba en OpenSees, validado contra SAP2000.
- **Verificación:** UZ techo = −0.0635 mm (SAP: −0.06375, 0.4 %).
  Equilibrio 0.000000.
- **Corrección:** el agente leía el momento con `eleForce` (ejes
  globales) como si fuera local; en vigas en Y parecía "torsión". Se
  detectó por simetría: vigas X e Y deben dar esfuerzos locales
  idénticos.

### Semana 2 — los dos edificios desde sus planos
- **Tarea:** ingestor de DXF reutilizable, modelo del LT2 y del edificio
  de Ingeniería, unión por la junta de dilatación, áreas tributarias a
  45°, cuatro casos de carga, visor Unity.
- **Corrección 1 — "en Z no hay calce".** El agente afirmó que los dos
  cuerpos compartían cotas comparando la *lista documentada* de niveles
  del edificio de Ingeniería, no su modelo, que estaba en alturas
  relativas. El cuerpo quedó flotando 7.97 m: su base caía en el
  segundo piso del otro. El equilibrio no lo vio (junta libre, cada
  cuerpo cierra solo). Se vio **mirándolo en Unity**. Corregido con
  `dz = −7.97` y una verificación de cotas en `conjunto/armar.py`.
- **Corrección 2 — ΔX medido al eje, no a la cara.** El LT2 quedó 12.5 cm
  metido en la junta. `armar.py` ahora mide caras y avisa si la
  separación no es la declarada.
- **Corrección 3 — el visor mostraba un archivo viejo.** El lanzador
  copiaba a `modelo_unity.json` y la escena abría
  `modelo_unity_edificio.json`. Varias rondas de "arreglos" sin efecto
  hasta leer `Player.log`. Ahora el nombre se lee de la escena.

### Semana 3 — casos base, superposición, capacidad HA
- **Tarea:** Q y EX/EY, superposición verificada contra corrida
  explícita, Fiber Section de columna y muro, curvas P-M, punto de
  demanda de cualquier elemento, verificación RC contra cálculo a mano.
- **Corrección 1 — la verificación de losa acusaba 194 barras.** El
  agente dividía la carga distribuida de G por el área tributaria sin
  descontar el **peso propio** de la barra, que viaja sumado. Se
  comprobó la hipótesis (16 vigas con `wz = 12.0` exacto = 0.48·25) y
  se declaró `incluye_peso_propio` en el caso.
- **Corrección 2 — el módulo elástico del conjunto.** Comparando el LT2
  dentro del conjunto contra el LT2 solo, los desplazamientos salían
  1.1180× mayores en los cinco pisos: √(28/35) = 0.8944. El contrato
  tiene un material y el merge se quedaba con el del primer cuerpo.
  Arreglado con `E`/`G` por sección; `verificar_conjunto.py` impide que
  vuelva.
- **Corrección 3 — "el vecino más cercano".** Para leer el fierro de un
  pilar el agente tomaba la llamada más cercana al rótulo, que es la de
  la **viga** del nudo (`34ED Ø10a10`). Se descubrió renderizando la
  elevación. La búsqueda quedó direccional.
- **Corrección 4 — la cota de redondeo.** La superposición "no cerraba"
  a 2.0e-8 contra una cota de 1.8e-8: faltaba el redondeo de la
  corrida explícita (+1 en Σ|λ|). Con la cota correcta el peor de 45
  casos da 1.000× la cota, no más.
- **Corrección 5 — caché de curvas P-M.** Indexada por número de barras
  y estribo, sin la sección: un muro de 1.45 m se comparaba contra la
  curva de uno de 7.95 m. Tres colisiones.
- **Corrección 6 — el merge de Eduardo.** Su Claude resolvió
  `capacidad_ha.py` a favor de la versión vieja (218 líneas) y perdió su
  propia Parte D (469); y restauró la versión del lanzador que toma el
  primer `nombreArchivo`, que con dos visores es el equivocado. Ambas
  detectadas corriendo la suite sobre el árbol mergeado.
- **Lo que el agente propuso y el grupo aceptó con reparos:** deducir
  el número de barras longitudinales del pilar desde el estribo (una
  traba = una barra intermedia). Es coherente con el plano pero es una
  inferencia; el diámetro sigue siendo supuesto y está declarado así.
- **Lo que el agente no forzó:** 9 de 40 muros quedan sin fierro porque
  sus llamadas `L:` marcan empalmes, no pisos; inventar la regla habría
  sido adivinar. `armar.py` los enumera.

---

## Verificaciones críticas del proyecto

| Qué | Valor | Dónde |
|---|---|---|
| Benchmark, UZ techo bajo G | −0.0635 mm | `benchmark/benchmark_distribuida.py` |
| LT2, G total | 34 148.98 kN, 232 nodos, 378 elementos | `edificios/lt2/verificar_lt2.py` |
| Conjunto, G total | 84 801.2 kN = suma de los cuerpos | `comun/calcular.py conjunto` |
| Cada cuerpo dentro del conjunto = cuerpo solo | 0.00e+00 m en el LT2 | `edificios/conjunto/verificar_conjunto.py` |
| Losa aplicada = losa dibujada | q constante por piso, 0 barras fuera | `comun/verificar_tributarias.py` |
| Corte basal = carga lateral | error < 1e-7 relativo | `comun/sismo.py` |
| Superposición = corrida explícita | ≤ 1.05× la cota de redondeo, 45/45 | `comun/combinar.py` |
| Tracción pura, fibras = a mano | 0.00e+00 | `semana03/verificar_rc.py` |
| Contrato JSON ↔ C# | sin campos huérfanos | `comun/test_contrato_unity.py` |

Todo junto: `python comun/verificar_todo.py`.
