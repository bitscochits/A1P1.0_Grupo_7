# CLAUDE.md — Lo que un agente tiene que saber antes de tocar este repo

> Contexto para Claude Code y cualquier otro agente de IA. Léelo entero
> antes de editar. El **flujo** del repo, archivo por archivo, está en
> `README.md`; acá van las reglas, las convenciones y las trampas que ya
> costaron tiempo. `AGENTS.md` es el registro de uso de IA que pide el
> curso.
>
> Repo: https://github.com/bitscochits/A1P3_Grupo_7 · Grupo 7 ·
> Métodos Computacionales en Obras Civiles, UAndes, 2026-02.

---

## 1. Qué es esto

Un laboratorio estructural digital del Edificio de Ingeniería de la
UAndes: **dos cuerpos** (el antiguo, planos `2017_67`; el nuevo LT2,
planos `2024_22`) separados por una junta de dilatación, modelados
desde sus planos DXF, resueltos con OpenSees, verificados
numéricamente y mostrados en Unity. No se evalúa realismo gráfico; se
evalúa corrección, verificación, trazabilidad y **que cada integrante
pueda explicar cualquier parte**.

## 2. La regla de oro

```
planos DXF → Python/OpenSees CALCULA → JSON es la fuente de verdad → Unity MUESTRA
```

Nunca lógica de cálculo estructural en C#. Si hay que calcular algo,
va en Python y viaja por JSON. Unity dibuja, y como mucho edita datos
que vuelven a Python para recalcular.

## 3. El pipeline de cuatro etapas

```
edificios/<ed>/planos/   →  data/geometria/<ed>.json     lo que DICE el plano
edificios/<ed>/armar.py  →  data/modelo/<ed>.json        el contrato neutro
comun/calcular.py        →  data/resultados/<ed>_<caso>.json
edificios/<ed>/exportar_unity.py → data/unity/<ed>.json   lo que dibuja el visor
```

`<ed>` es `lt2`, `ingenieria` o `conjunto`. **`data/modelo/` es donde
los dos edificios hablan el mismo idioma** y donde `conjunto/armar.py`
los une: aplica el calce, renumera tags y respeta la junta libre.
`comun/calcular.py` no sabe de qué edificio se trata.

**Una carpeta = un dueño.** `edificios/lt2/` y `edificios/ingenieria/`
se editan por separado; `comun/` y `unity/` son compartidos y se avisa
antes de tocarlos. Nada específico de un edificio va en código: va en
`edificios/<ed>/perfiles/*.json` (capas, ventanas, supuestos).

## 4. Convenciones que no se rompen

| Convención | Regla | Dónde vive |
|---|---|---|
| **Ejes** | OpenSees: Z vertical. Unity: Y vertical. `Unity(x, z, y)`. | `VisorEstructura.cs` |
| **Unidades** | m, kN, kPa. `Ec = 4700·√f'c·1000`. | todo el repo |
| **Inercias** | En el contrato `Iz` es la de **gravedad** (`b·h³/12`), `Iy` la lateral. El servidor las **cruza** solo en elementos no verticales (`vecxz=(0,0,1)` deja el local *y* vertical). | `servidor_opensees.py` |
| **`vecxz`** | Se elige por **geometría**, nunca por la etiqueta `tipo`. Vertical → `(1,0,0)`; si no → `(0,0,1)`. Un muro trae el suyo (su normal). | `servidor_opensees.py` |
| **Fuerzas internas** | `eleResponse(tag,'localForce')`, **nunca** `eleForce` (que es global). Vector `[N,Vy,Vz,T,My,Mz]` por extremo. | `calcular.py`, `demanda_capacidad.py` |
| **Reacciones** | `nodeReaction` en un nodo de diafragma incluye la fuerza de la restricción, que es interna. Se separa **por grado de libertad**: en horizontal solo cuentan nodos fuera de todo diafragma; en vertical, cualquier restringido salvo el maestro. Sumar todo **dobla el corte basal**. | `calcular.equilibrio()` |
| **Diafragma rígido** | `constraints('Transformation')`. Los GDL fuera del plano del maestro se fijan. El piso se traslada **y gira**: `ux_i = ux_m − rz·(y_i−y_m)`. | `servidor_opensees.py` |
| **Muro** | Una barra en su eje baricéntrico (columna ancha) + brazos rígidos como barras ×100 hasta las caras. **No** `rigidLink` (pelea con el diafragma). | `malla.py`, `modelo_lt2.py` |
| **E por sección** | `E`/`G` opcionales en cada sección pisan al material del modelo. Es lo que permite juntar un cuerpo G35 con uno G28. | `conjunto/armar.py` |
| **Rutas** | Solo `comun/rutas.py` sabe dónde está cada cosa; encuentra la raíz subiendo hasta la marca del repo. **Nunca** contar `dirname`. | `rutas.py` |
| **Resultados** | El servidor **redondea**: desplazamientos a 8 decimales, fuerzas a 4. Nada se puede comparar por debajo de eso. | `combinar.py` |

## 5. Supuestos declarados (no están en el código)

Todo lo que el plano no dice vive en `edificios/<ed>/perfiles/*.json`
con su justificación al lado, para que se vea como supuesto y se pueda
reemplazar sin tocar código:

- **Sismo**: coeficiente basal, fracción de sobrecarga en el peso
  sísmico y patrón en altura. Los define el profesor; se sobreescriben
  por línea de comandos (`--cs`, `--q`, `--patron`, `--comb`).
- **Diámetro longitudinal de los pilares del LT2**: el plano da el
  estribo y las trabas; el número de barras se deduce del estribo (una
  traba amarra una barra) y **solo el diámetro es supuesto** (Ø25).
- **Junta de dilatación**: 5 cm. De ahí sale el `dx` del calce.
- **Dinteles** del LT2 y el hormigón del pilar de Ingeniería (lámina
  típica): declarados, no extraídos.

## 6. Trampas que ya costaron tiempo (y dónde está el guardia)

Todas fallan **en silencio**: el modelo corre, da números, y el error
solo se ve mirando otra cosa.

| Trampa | Guardia |
|---|---|
| El globo de un eje del DXF no está sobre su eje (va con un quiebre). | `verificar_planos.py` |
| Cada lámina/XREF tiene **su propio origen**; la 305 trae dos elevaciones. | `enfierradura.hojas_de_elevacion()` |
| `JsonUtility` ignora sin avisar un campo C# que no calza con el JSON: deformada plana, sin error. | `comun/test_contrato_unity.py` |
| La **escena** pisa el `nombreArchivo` del C#, y hay dos visores: el lanzador debe leer el de `VisorEstructura`. | `lanzar_unity.nombre_que_lee_el_visor()` |
| En la elevación, la llamada de fierro **más cercana** al pilar es la de la viga. La búsqueda es direccional (hacia abajo, dentro del ancho). | `enfierradura.extraer()` |
| El plano arma muros de dos formas: **malla** (bloque con atributos) o **machón** (`E`+`L:n+n`). Una elevación sin pilares también tiene muros. | `enfierradura.py`, `exportar_unity.pegar_enfierradura_muros()` |
| Al unir dos edificios el contrato tiene **un** material: el LT2 corría con 28 MPa (10.6% más blando) y el equilibrio cerraba igual. | `verificar_conjunto.py` |
| Un paño de losa que nunca entró al modelo **no** rompe el equilibrio. | `verificar_tributarias.py` (q implícito por piso) |
| Dos secciones con el mismo número de barras **no** son la misma sección (caché de curvas P-M). | `demanda_capacidad._todas()` |
| Un cociente de torsión sobre un piso que casi no se mueve es ruido. | `sismo.py` |
| Ajustar un umbral "hasta que entre" roba las anotaciones del vecino. Regla: mínima distancia, a uno solo. | `pegar_enfierradura_muros()` |

## 7. Reglas para el agente

1. **Toda** modificación al modelo o a las cargas termina corriendo
   `python comun/verificar_todo.py`. Si algo falla, se dice con la
   salida; no se relaja la tolerancia para que pase.
2. Cuando una verificación marque algo, **primero** sospechar de la
   verificación y comprobar la hipótesis (así apareció el peso propio
   en la carga distribuida, el +1 de la cota de redondeo y el
   confinamiento en el balanceado).
3. Una tolerancia se **mide** contra su causa (redondeo, muestreo), no
   se elige a ojo.
4. Una sola definición de cada cosa: la sección de fibras que se
   resuelve es la que se dibuja; el `nombreArchivo` lo manda la
   escena; el área tributaria vive en el elemento.
5. Lo leído del plano y lo supuesto se distinguen **en el dato**
   (`origen`, `_supuesto`, `provisorio`), no en la memoria de nadie.
6. No tocar `edificios/<otro>/` sin avisar. Avisar antes de tocar
   `comun/` o `unity/`.
7. Mensajes de commit que digan **por qué** y qué se comprobó, con los
   números.

## 8. Cómo saber si está todo bien

```bash
python comun/verificar_todo.py            # la suite entera
python comun/verificar_todo.py --rapido   # sin los lentos
```

Números de control: LT2 `G = 34 148.98 kN`, 232 nodos / 378 elementos;
Ingeniería `G = 50 652.2 kN`; conjunto `G = 84 801.2 kN` = la suma;
benchmark de Semana 1 `UZ techo = −0.0635 mm`.
