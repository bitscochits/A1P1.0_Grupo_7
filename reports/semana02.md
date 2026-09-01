# Semana 2 — Modelo global v1 y transferencia de cargas

**Edificio de Ingeniería, Universidad de los Andes**
Grupo 7 · Laboratorio estructural digital

Todos los números de este informe salen de correr `benchmark_3d.py` y
`export_unity.py`. Ninguno está escrito a mano.

```bash
python benchmark_3d.py     # modelo, 4 casos, equilibrio
python export_unity.py     # exporta a Unity + round-trip por el servidor
```

---

## 1. Trazabilidad desde planos

La grilla sale de los ejes estructurales de los planos DXF. Cada eje es
una coordenada; el cruce de dos ejes en un nivel es un nodo; cada nodo
se conecta con sus vecinos por elementos.

### Verificación contra los planos

Los ejes del modelo se contrastaron contra la capa `RLE-EJE` del plano
`2017_67-100` (fundaciones), leído con `ezdxf`. **Las unidades del DXF
son centímetros.**

Los **8 ejes X del modelo existen todos** en el plano, con coincidencia
al centímetro:

| eje del plano | plano (m) | modelo (m) |
|---|---|---|
| E | 8.021 | 8.02 ✓ |
| Ea | 11.321 | 11.32 ✓ |
| Ed | 14.721 | 14.72 ✓ |
| F | 18.021 | 18.02 ✓ |
| G | 28.021 | 28.02 ✓ |
| H | 38.021 | 38.02 ✓ |
| I | 48.021 | 48.02 ✓ |
| I' | 53.021 | 53.02 ✓ |

En **Y, dos de los seis no existen** en ninguna lámina (`-100`, `-101`,
`-102`, `-103`):

| modelo (m) | plano | |
|---|---|---|
| **46.92** | — | ✗ **no corresponde a ningún eje** |
| 50.26 | 50.256 | ✓ |
| 55.20 | 55.201 | ✓ |
| 60.20 | 60.201 | ✓ |
| **65.22** | — | ✗ **no corresponde a ningún eje** |
| 72.75 | 72.751 | ✓ |

El plano tiene 19 ejes X y 18 ejes Y; el modelo usa un subconjunto, lo
cual es legítimo como simplificación. Lo que no lo es son esos dos
valores que no salen de ningún lado.

### Ejes

| dirección | valores (m) |
|---|---|
| X (8 ejes) | 8.02, 11.32, 14.72, 18.02, 28.02, 38.02, 48.02, 53.02 |
| Y (6 ejes) | 46.92, 50.26, 55.20, 60.20, 65.22, 72.75 |
| Z (9 niveles) | 0.0, 4.0, 7.5, 11.0, 14.5, 18.0, 21.5, 25.0, 28.5 |

Las cotas no son uniformes: el primer piso tiene 4.00 m y los demás
3.50 m. Los ejes X tampoco: hay vanos de 3.30 m y otros de 10.00 m, lo
que después será determinante en el reparto de cargas (§4).

### Numeración

```
nodo(nivel, ix, iy) = nivel · 48 + ix · 6 + iy + 1
```

con 48 = 8 × 6 nodos por piso. Los nodos de la base son 1 a 48.

### Ejemplo completo: plano → nodo → elemento → sección → tag

| paso | valor |
|---|---|
| **Plano** | cruce del eje X = 8.02 m con el eje Y = 46.92 m |
| **Nodo base** | `ix=0, iy=0, nivel=0` → **nodo 1** en (8.02, 46.92, 0.00) |
| **Nodo piso 1** | `nivel=1` → **nodo 49** en (8.02, 46.92, 4.00) |
| **Elemento** | columna que une 1 → 49 |
| **elementTag** | **1** |
| **sectionTag** | `"columna"` |
| **Sección** | 0.50 × 0.50 m, A = 0.2500 m², J = 8.802e-3 m⁴ |

Un segundo ejemplo, esta vez una viga:

| paso | valor |
|---|---|
| **Plano** | vano entre los ejes X = 28.02 y X = 38.02, sobre el eje Y = 55.20 |
| **Nodos** | `nivel=1, ix=4, iy=2` → **nodo 75** a **nodo 81** |
| **elementTag** | **411** |
| **sectionTag** | `"viga_x"` (0.30 × 0.60 m) |
| **Luz** | 10.00 m |

### Rangos de tags

| rango | qué |
|---|---|
| 1 – 384 | columnas |
| 385 – 720 | vigas en X |
| 721 – 1040 | vigas en Y |

---

## 2. Estadísticas del modelo

| concepto | cantidad |
|---|---|
| Nodos estructurales | **432** |
| Nodos de muro | **36** |
| Nodos maestros de diafragma | **8** |
| Nodos totales | **476** |
| Columnas | **384** |
| Vigas en X | **336** |
| Vigas en Y | **320** |
| Vigas totales | **656** |
| Muros | **32** (4 muros × 8 niveles) |
| Diafragmas rígidos | **8** |
| Pisos con losa | **8** |
| Niveles (incluida la base) | **9** |
| Elementos totales | **1072** |
| Paños de losa por piso | **35** |
| Área de piso | **1162.35 m²** |
| Altura total | **28.50 m** |
| Planta | 45.0 × 25.8 m |

### Muros

> ⚠️ **La ubicación de los muros es INCORRECTA. Verificada contra los
> planos y desmentida.**
>
> Los muros del modelo se pusieron como un supuesto (un núcleo de
> 3.3 m en el extremo poniente). Al conseguir los planos y leer la capa
> `RLE-MURO` del DXF, resultó que los muros reales son **muros largos de
> 15 a 28 m**, no un núcleo compacto:
>
> | eje X (m) | espesor | se extiende en Y |
> |---|---|---|
> | 7.67 / 7.87 | 0.20 | 47.60 → 72.86 (**25.3 m**, fachada poniente) |
> | 18.07 / 18.37 | 0.30 | 48.30 → 63.75 (**15.5 m**) |
> | 48.02 / 48.32 | 0.30 | 37.78 → 63.75 (**26.0 m**) |
> | 53.27 / 53.57 | 0.30 | 64.55 → 75.58 (**11.0 m**) |
>
> Los muros del modelo (4 de 3.3 m) **subestiman groseramente** la
> rigidez lateral real. Los resultados de EX/EY hay que tomarlos como
> indicativos, no como valores de diseño.
>
> Se dejan en el modelo porque demuestran la capacidad (columna ancha,
> `vecxz`, torsión por excentricidad) y porque el reemplazo requiere
> alinear las láminas entre sí: **cada plano está insertado en un origen
> de coordenadas distinto**, así que combinarlos exige referenciarlos por
> su grilla de ejes. Es el primer punto de la Semana 3.

Modelo: **columna ancha**. Cada muro es un elemento vertical en su eje,
con la sección orientada por `vecxz` para que el eje fuerte quede en el
plano del muro. Sus nodos entran al diafragma de cada piso, que es lo que
lo conecta al resto de la planta.

| muro | dirección | ubicación | largo (m) | espesor (m) |
|---|---|---|---|---|
| 0 | Y | eje X = 8.02 | 3.34 | 0.25 |
| 1 | Y | eje X = 18.02 | 3.34 | 0.25 |
| 2 | X | eje Y = 46.92 | 3.30 | 0.25 |
| 3 | X | eje Y = 50.26 | 3.30 | 0.25 |

**Limitación:** sin brazos rígidos, las vigas que llegarían a las *caras*
del muro se conectan a su eje, o sea que el muro se comporta como si
tuviera ancho cero en esa unión. El servidor ya soporta
`brazos_rigidos`; agregarlos es el siguiente refinamiento.

### Material y secciones

Hormigón **G-28**: `f'c = 28 MPa`, `Ec = 4700·√f'c = 24 870 MPa`, ν = 0.2.

| sección | b × h (m) | A (m²) | Iy (m⁴) | Iz (m⁴) | J (m⁴) |
|---|---|---|---|---|---|
| columna | 0.50 × 0.50 | 0.2500 | 5.208e-3 | 5.208e-3 | **8.802e-3** |
| viga X | 0.30 × 0.60 | 0.1800 | 5.400e-3 | 1.350e-3 | **3.708e-3** |
| viga Y | 0.30 × 0.80 | 0.2400 | 1.280e-2 | 1.800e-3 | **5.502e-3** |

`J` se calcula con la fórmula de Saint-Venant para sección rectangular
llena (`modelo_benchmark.J_rectangular`). Ver §10: antes se usaba una
expresión incorrecta.

---

## 3. Carga superficial

| componente | valor |
|---|---|
| Espesor de losa | `t = 0.25 m` |
| Peso unitario del hormigón | `γ = 25.0 kN/m³` |
| Peso propio de la losa | `γ · t = ` **6.25 kN/m²** |
| Terminaciones y sobrelosa | **1.50 kN/m²** |
| **`q_G`** (carga muerta superficial) | **7.75 kN/m²** |
| **`q_Q`** (sobrecarga de uso) | **2.00 kN/m²** |

Por piso, la carga muerta de losa es:

```
q_G · A_piso = 7.75 · 1162.35 = 9008.21 kN
```

A eso se suma el peso propio de vigas (aplicado como carga distribuida
adicional sobre cada barra) y de columnas (como fuerzas nodales en sus
extremos). El total de la carga muerta del edificio es **100 254.42 kN**.

---

## 4. Áreas tributarias

### Criterio

Cada paño de losa se reparte a las **cuatro vigas que lo bordean**,
trazando bisectrices a 45° desde las esquinas. Eso divide el paño en
cuatro polígonos:

```
    paño Lx × Ly, con Ly < Lx

    +--------------------------+
    | \                      / |   vigas de luz Lx (LARGAS) -> TRAPECIO
    |  \____________________/  |
    |  /                    \  |   vigas de luz Ly (CORTAS) -> TRIÁNGULO
    | /                      \ |
    +--------------------------+
```

Con `a` = luz de la viga y `b` = luz transversal del paño:

| caso | polígono | área |
|---|---|---|
| `b ≤ a` (viga larga) | trapecio | `b(2a − b)/4` |
| `b > a` (viga corta) | triángulo | `a²/4` |

Una **viga interior borda dos paños**, así que acumula las dos
contribuciones. El reparto se implementa iterando **por paño** y sumando
sus cuatro aportes, de modo que la conservación queda garantizada por
construcción.

La carga se aplica como **uniforme equivalente** sobre la barra:

```
w = q_G · A_tributaria / L        [kN/m]
```

usando `eleLoad -beamUniform`, no como fuerzas puntuales en los nudos
(ver §10).

### Ejemplos de paños

| paño (ix, iy) | Lx (m) | Ly (m) | A paño (m²) | viga X | A_x (m²) | viga Y | A_y (m²) |
|---|---|---|---|---|---|---|---|
| (0,0) | 3.30 | 3.34 | 11.02 | triángulo | 2.723 | trapecio | 2.788 |
| (0,1) | 3.30 | 4.94 | 16.30 | triángulo | 2.723 | trapecio | 5.429 |
| (0,4) | 3.30 | 7.53 | 24.85 | triángulo | 2.723 | trapecio | 9.702 |

Comprobación por paño: `2·A_x + 2·A_y = A_paño`.
Para (0,0): `2(2.723) + 2(2.788) = 11.02 m²` ✓

### Tres vigas en detalle (nivel 1)

| elementTag | dir | polígono(s) | L (m) | A_trib (m²) | q_G (kN/m²) | carga total (kN) | w aplicada (kN/m) |
|---|---|---|---|---|---|---|---|
| **385** | X | 1 triángulo (borde) | 3.30 | 2.723 | 7.75 | 21.10 | 6.394 |
| **411** | X | 2 trapecios (interior) | 10.00 | 37.349 | 7.75 | 289.46 | 28.946 |
| **737** | Y | 2 trapecios (interior) | 4.94 | 11.529 | 7.75 | 89.35 | 18.088 |

La viga 385 es de borde y de vano corto: recibe un solo triángulo. La
411 tiene 10 m de luz y es interior: recibe casi **14 veces** más área.
Ese contraste es exactamente lo que un reparto 50/50 por franjas no
captura.

En Unity, seleccionar una viga muestra su `área tributaria` y su
`w gravedad` en el panel (§8).

---

## 5. Conservación

La suma de todas las áreas tributarias de un piso debe igualar el área
del piso:

```
Σ A_tributaria  =  1162.350000 m²
A_piso          =  1162.350000 m²
error           =  2.274e-13 m²   (1.96e-14 %)
```

Y en carga:

```
Σ (q_G · A_trib)  =  q_G · A_piso  =  9008.21 kN por piso
```

**Tolerancia adoptada: 1e-6 m² en área y 1e-6 kN en fuerza.** El error
obtenido está 7 órdenes de magnitud por debajo — es puro redondeo de
punto flotante.

### Equilibrio global de los cuatro casos

| caso | aplicado (kN) | reacciones (kN) | error (kN) |
|---|---|---|---|
| G | 100 254.42 | 100 254.42 | 0.0002 |
| Q | 18 597.60 | 18 597.60 | 0.0002 |
| EX | 9 965.44 | −9 965.44 | 0.0000 |
| EY | 9 965.44 | −9 965.44 | 0.0004 |

> **El equilibrio NO valida el reparto.** Si a una viga se le da el doble
> y a la vecina la mitad, la suma de reacciones cierra igual de bien.
> Por eso la verificación de §5 (conservación de área, viga por viga) es
> independiente y necesaria. Este punto nos costó un error real: ver §10.

### Desplazamientos máximos

| caso | UX (m) | UY (m) | UZ (m) |
|---|---|---|---|
| G | 0.00152 | 0.00274 | **0.01180** |
| Q | 0.00036 | 0.00065 | 0.00250 |
| EX | **0.09279** | 0.00000 | 0.00304 |
| EY | 0.00000 | **0.06195** | 0.00221 |

Deriva de techo bajo EX: `0.0928 / 28.5 = 1/307`.

---

## 6. Apoyos y restricciones

El modelo usa tres tipos de condición de borde. El orden de los grados
de libertad es `[ux, uy, uz, rx, ry, rz]`, donde `1` = restringido.

| tipo | nodos | restricciones | dónde |
|---|---|---|---|
| **Empotramiento** | 48 | `[1,1,1,1,1,1]` | los 48 nodos de la base (nivel 0) |
| **Libre** | 384 | `[0,0,0,0,0,0]` | todos los nodos de piso |
| **Maestro de diafragma** | 8 | `[0,0,1,1,1,0]` | un nodo por piso, en el centro |

### Por qué el maestro lleva restricciones

El diafragma solo ata los grados de libertad **en su plano** (`ux`, `uy`,
`rz`). Los de fuera del plano (`uz`, `rx`, `ry`) del nodo maestro quedan
sueltos, y como ese nodo **no tiene ningún elemento conectado**, la
matriz de rigidez saldría singular. Por eso se restringen explícitamente.

El servidor hace esto solo y lo reporta en `avisos` cuando recibe un
diafragma cuyo maestro no está restringido.

### En el visor

Los nodos con alguna restricción se dibujan en **verde**; los libres en
azul; los maestros de diafragma en gris y más pequeños (`auxiliar: true`).

---

## 7. Diafragmas rígidos

### Cinemática

Un diafragma rígido hace que el piso se mueva como **cuerpo rígido en su
plano**. Eso **no** significa que todos los nodos tengan el mismo
desplazamiento: significa que se cumple

```
ux_i = ux_m − rz · (y_i − y_m)
uy_i = uy_m + rz · (x_i − x_m)
rz_i = rz_m
```

donde `m` es el nodo maestro. El piso puede **trasladarse y rotar**; lo
que no puede es deformarse en su plano.

Confundir esto es un error fácil, y lo cometimos: ver §10.

### Implementación

```python
ops.rigidDiaphragm(3, maestro, *esclavos)   # 3 = perpendicular a Z
ops.constraints('Transformation')            # 'Plain' no sabe imponerlo
```

Un diafragma por piso (8 en total), con el nodo maestro en el **centro
geométrico** de la planta, que es donde se aplica el corte sísmico.

### Verificación numérica

Se comprobó, para los 8 pisos bajo EX, que (a) todos los nodos de un
piso comparten el mismo `rz` y (b) se cumple la relación de cuerpo
rígido:

| nivel | maestro | ¿`rz` común? | error de cuerpo rígido (m) |
|---|---|---|---|
| 1 | 433 | sí | 0.00e+00 |
| 2 | 434 | sí | 0.00e+00 |
| 3 | 435 | sí | 0.00e+00 |
| 4 | 436 | sí | 0.00e+00 |
| 5 | 437 | sí | 0.00e+00 |
| 6 | 438 | sí | 0.00e+00 |
| 7 | 439 | sí | 0.00e+00 |
| 8 | 440 | sí | 0.00e+00 |

Con la carga aplicada en el centro geométrico, `rz = 0` en todos los
pisos: la planta es regular en cada dirección, así que el centro de
rigidez coincide con el de aplicación y no hay torsión.

**Para demostrar que el diafragma sí permite rotar**, se repitió EX
aplicando la carga en una esquina del piso (excentricidad extrema):

| nivel | `rz` (rad) | error de cuerpo rígido (m) |
|---|---|---|
| 1 | 7.488e-04 | 1.69e-07 |
| 4 | 3.821e-03 | 1.46e-07 |
| 8 | **6.206e-03** | 1.86e-07 |

El piso rota (`rz` hasta 6.2e-3 rad) y **sigue siendo cuerpo rígido**
(error 1.9e-7 m, que es el piso de redondeo del JSON, con 8 decimales
sobre desplazamientos de ~0.1 m).

### Torsión real del edificio

Al incorporar los muros, EX deja de ser un caso puramente traslacional:
los cuatro muros están en el extremo poniente, así que el centro de
rigidez se corre y **el edificio torsiona**.

| nivel | `ux` del maestro (m) | `rz` (rad) | error de cuerpo rígido (m) |
|---|---|---|---|
| 1 | 0.011633 | −2.143e-04 | 6.65e-08 |
| 4 | 0.085745 | −8.701e-04 | 1.64e-07 |
| 8 | 0.171462 | −9.534e-04 | 7.80e-08 |

Y aparece `UY = 0.0085 m` bajo EX, que es desplazamiento transversal puro
producto del giro.

Esta es la prueba de que la corrección de §10 era necesaria: con el
`equalDOF` anterior, `rz` habría salido 0 en los tres casos, y **la
torsión inducida por los muros habría sido invisible**.

---

## 8. Viewer Unity

El proyecto vive en `unity/` dentro del repositorio. Tres scripts de
responsabilidad separada más dos de interacción:

| script | responsabilidad |
|---|---|
| `ModeloEstructural.cs` | clases de datos — el contrato con el JSON |
| `VisorEstructura.cs` | solo dibuja |
| `AnalizadorEstructural.cs` | solo habla con el servidor |
| `CamaraOrbital.cs` | navegación |
| `EditorEstructura.cs` | selección y edición |

### Capas

Toggles independientes para: **nodos**, **nodos auxiliares**,
**columnas**, **vigas**, **muros** y **deformada**. Cada uno redibuja al
instante, en pleno Play.

### Selección e IDs

Click sobre un nodo o una barra la selecciona (raycast sobre los
componentes `DatoNodo` / `DatoElemento`, que llevan el tag de OpenSees).
El panel muestra:

- **nodo**: `id`, coordenadas X/Y/Z editables, si está empotrado,
  y `UX / UY / UZ` del último análisis
- **barra**: `id`, nodos que conecta, `tipo`, `sección`,
  **área tributaria (m²)**, **w gravedad (kN/m)**, y `N / Vz / My` en
  **ejes locales**

Los objetos de la escena se nombran `Nodo_49`, `NodoAux_433`,
`Elem_411_viga_x`, así que el id es visible también en la Hierarchy.

### Ejes

La conversión OpenSees → Unity está centralizada en `Ejes.AUnity()`:

```
Unity(x, z_opensees, y_opensees)
```

OpenSees usa **Z vertical** (convención de ingeniería); Unity usa **Y
vertical**. Si el edificio se ve acostado, el error está en ese único
punto.

Los **ejes locales de cada barra** todavía no se dibujan; los esfuerzos
sí se reportan en ejes locales, que es lo que importa para leerlos.

### Apoyos

Los nodos con restricción se pintan verde; los libres, azul; los
maestros de diafragma, gris y más chicos.

### Áreas tributarias

Al seleccionar una viga, el visor **dibuja el contorno de su polígono
tributario** sobre la losa, en ámbar, y el panel muestra:

```
area tributaria: 37.349 m2
w gravedad:      28.946 kN/m
poligono dibujado: 37.349 m2  (calza)
```

Esa última línea es una verificación visible: el área del polígono que se
está dibujando tiene que coincidir con la que se usó para calcular la
carga. Si difieren, el panel lo dice.

La **geometría del polígono se calcula en Python**
(`modelo_benchmark.poligonos_tributarios`) y se exporta en el JSON; Unity
solo la dibuja. Se verificó que el área del polígono coincide con la de
`area_tributaria_viga()` con discrepancia **0.00e+00**, y que los 140
polígonos de un piso suman exactamente los 1162.35 m² del piso.

Solo se dibuja el de la barra seleccionada: hay 1120 polígonos en el
edificio y pintarlos todos serían miles de objetos.

---

## 9. Modificación del modelo

`EditorEstructura.cs` permite editar el modelo dentro de Unity, sin
tocar el JSON a mano. Está implementado:

| operación | cómo |
|---|---|
| **Cambiar sección** | seleccionar barra → botón con el nombre de la sección |
| **Cambiar apoyo** | seleccionar nodo → toggle *Empotrado* |
| **Mover un nodo** | arrastrarlo (planta) o Shift+arrastrar (altura), o campos X/Y/Z |
| **Crear barra** | seleccionar nodo A → *Empezar barra* → seleccionar nodo B → elegir sección |
| **Borrar** | tecla Supr |
| **Recalcular** | Enter → manda el modelo al servidor y dibuja la deformada nueva |

El reanálisis desde Unity **ya funciona**, aunque para esta entrega no
era obligatorio.

### Integridad al borrar

Borrar deja referencias huérfanas, y algunas son peligrosas porque **no
fallan**: si se borra una barra y queda su carga distribuida, OpenSees
emite un warning por consola y **descarta la carga**. El análisis
"funciona" con menos carga de la que uno cree, y el equilibrio cierra
igual porque la carga descartada nunca entró.

Por eso el editor limpia también las cargas, las barras conectadas, los
diafragmas y los brazos rígidos que apuntaban a lo borrado. Y el
servidor lo valida de forma independiente:

```
En 'G': hay una carga sobre el elemento 5, que no existe.
Si lo borraste, borra tambien su carga.
```

---

## 10. Uso de IA: errores propuestos por el agente y su corrección

El agente (Claude) participó como revisor y como implementador. Lo que
sigue son errores **reales** encontrados y corregidos, con el número que
los delató.

### 10.1 Error del agente, corregido por el test

Al implementar la subdivisión de vigas del benchmark, el agente dejó
esta línea:

```python
nodos_techo = [nid for nid in coords if nid > mb.nNodosPorPiso]
```

Con la subdivisión, "todo nodo por encima de la base" pasó a incluir los
12 nodos intermedios nuevos. El sismo saltó de **4 × 50 = 200 kN** a
**16 × 50 = 800 kN** sin ningún mensaje de error: el modelo convergía y
el equilibrio cerraba, porque el equilibrio compara reacciones contra lo
aplicado, y lo aplicado también estaba mal.

Lo detectó `test_contrato_unity.py`, que compara contra el valor
**esperado independientemente** (200 kN), no contra lo que el modelo
aplicó:

```
[FALLA] equilibrio EX   fx = -800.0000 kN (esperado -200.0)
```

Corrección: tomar solo los nudos del marco.

```python
nodos_techo = list(range(mb.nNodosPorPiso + 1, 2 * mb.nNodosPorPiso + 1))
```

**Lección:** una verificación que se compara consigo misma no verifica
nada. La referencia tiene que venir de afuera del modelo.

### 10.2 `eleForce` devuelve ejes GLOBALES

El código leía `ops.eleForce(tag)` etiquetando la salida como
`[N, Vy, Vz, T, My, Mz]`, que es notación **local**. No lo es.

Para vigas que corren en X funcionaba por casualidad (su eje local x
coincide con el global X). Para vigas en Y, el momento de gravedad
aparecía en la casilla de **torsión**, y la viga parecía no flectar.

Se detectó con un chequeo de **simetría**: en un marco cuadrado, las
vigas X e Y deben tener esfuerzos locales idénticos.

```
VIGA X:  eleForce (GLOBAL) My = -4.1711     localForce  My = -4.1711
VIGA Y:  eleForce (GLOBAL) Mx = +4.1711     localForce  My = -4.1711
                           ^^ el flector en la casilla de torsión
```

Corrección: `ops.eleResponse(tag, 'localForce')`.

### 10.3 El `equalDOF` no era un diafragma

El modelo del edificio tenía:

```python
ops.equalDOF(master, slave, 1, 2, 6)     # ux, uy, rz IGUALES
```

Eso obliga a que **todos los nodos del piso tengan el mismo `ux`**, o
sea que el piso solo puede trasladarse y **nunca rotar**. La torsión del
edificio quedaba fuera del modelo. Además, `constraints('Plain')` no
sabe imponer un `rigidDiaphragm` real.

Corrección: `ops.rigidDiaphragm(3, maestro, *esclavos)` con
`constraints('Transformation')`, y verificación numérica de la
cinemática (§7), incluyendo el caso excéntrico que demuestra que ahora
el piso **sí** rota.

### 10.4 Torsión `J` sin fórmula

```python
J_col = min(Iy_col, Iz_col) * 0.3
```

Esa expresión no corresponde a ninguna fórmula conocida. Contra
Saint-Venant:

| sección | J usado | J real | factor |
|---|---|---|---|
| columna 50×50 | 1.562e-3 | 8.802e-3 | **5.6×** |
| viga X 30×60 | 4.050e-4 | 3.708e-3 | **9.2×** |
| viga Y 30×80 | 5.400e-4 | 5.502e-3 | **10.2×** |

En un marco cuadrado simétrico no se nota. En un edificio de 9 niveles
con planta irregular bajo sismo, sí.

### 10.5 Cargas puntuales en vez de distribuidas

La carga de losa se aplicaba como dos fuerzas en los extremos de cada
viga:

```python
F = w * dx / 2.0
ops.load(n1, 0, 0, -F, 0, 0, 0)
```

La carga total se conservaba —el equilibrio cerraba— pero **las vigas no
flectaban por la losa**: todo el momento del vano desaparecía. Para
dimensionar vigas, eso invalida el resultado.

Corrección: `eleLoad -beamUniform` con la carga tributaria.

### 10.6 Sismo dos órdenes de magnitud bajo

```python
F = 10.0 * lev      # 360 kN de corte basal
```

Contra un peso sísmico de ~100 000 kN, eso es un coeficiente de
**0.36 %**. Se reemplazó por un corte basal `V = C · W` con `C = 0.10`,
repartido en altura según `F_i = V · W_i·h_i / Σ W_j·h_j`.

Sigue siendo pseudoestático: **falta el espectro NCh433, el factor R, la
zona sísmica y el tipo de suelo**. Está marcado como tal en el código.

### 10.7 Un "error" que resultó no serlo

Al verificar el diafragma, el primer test que escribió el agente
comprobaba que todos los nodos del piso tuvieran el **mismo `ux`**. El
test falló, y la conclusión inmediata fue que el diafragma no
funcionaba.

Estaba mal el test, no el código: un diafragma es rígido *en su plano* y
con carga excéntrica **rota**, así que los `ux` difieren legítimamente.
Lo correcto es verificar la relación de cuerpo rígido, que cierra con
error 0.

**Lección:** cuando un test falla, el sospechoso número uno es el test.

---

## 11. Pendientes

| tema | estado |
|---|---|
| **Ubicación real de los muros** | **verificada y DESMENTIDA**; los reales son de 15–28 m, no de 3.3 m |
| **Ejes Y = 46.92 y 65.22** | **no existen en los planos**; hay que reemplazarlos o justificarlos |
| Alinear las láminas entre sí | cada plano tiene su propio origen de coordenadas |
| Brazos rígidos en la unión viga-muro | pendiente; hoy el muro tiene ancho cero en esa unión |
| Ejes locales dibujados en Unity | pendiente |
| Espectro NCh433 completo | pendiente; hoy `C = 0.10` fijo |
| Fiber Sections / no lineal | pendiente (Semana 4+) |
| Peso propio de columnas como carga distribuida | hoy va como fuerzas nodales |

---

## Reproducibilidad

```bash
python benchmark_3d.py              # modelo + 4 casos + equilibrio
python export_unity.py              # exporta a Unity + round-trip
python test_areas_tributarias.py    # conservación y geometría del reparto
python test_servidor.py             # multi-caso, diafragmas, apoyos
python test_contrato_unity.py       # campos C# ↔ JSON
python benchmark_distribuida.py     # benchmark Semana 1 (−0.06348 mm)
```

Los seis terminan indicando si algo se rompió.
