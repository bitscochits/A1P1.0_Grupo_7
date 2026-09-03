# Geometria extraida de los planos

**Proyecto:** LT2 - Proyecto de calculo 2024_22 (M. Kupfer C., octubre 2024)  
**Perfil:** `lt2_2024_22.json`  
**Planos:** `C:\Users\Administrador\OneDrive\Escritorio\UANDES\202602\Metodos computacionales\P1\Planos\LT2_CAL_dxf`  
**Unidades:** m  (el dibujo estaba en cm)


## Ejes (lamina de referencia: `2024_22-101`)

| Direccion | Ejes |
|---|---|
| vertical, x constante (10) | **A'**=10.965 · **A**=14.745 · **B**=22.245 · **C**=32.236 · **B'**=35.415 · **C'**=39.787 · **D**=42.236 · **E1**=42.407 · **D'**=42.919 · **E'**=43.747 |
| horizontal, y constante (8) | **3**=11.047 · **2A'**=15.312 · **2**=18.297 · **1A'**=22.932 · **1'**=23.992 · **1**=27.197 · **8A**=33.617 · **8B**=37.917 |

## Niveles

Confirmados por **todas** las elevaciones: `-8.57, -7.97, -4.01, -0.05, +3.91, +7.87, +11.83`

Alturas entre niveles: `0.60, 3.96, 3.96, 3.96, 3.96, 3.96`


| Cota z (m) | En cuantas elevaciones | Laminas |
|---:|---:|---|
|   -9.770 | 5 | 300, 301, 303, 304, 305 |
|   -9.570 | 5 | 300, 302, 303, 304, 305 |
|   -9.530 | 2 | 302, 304 |
|   -9.170 | 1 | 301 |
|   -8.930 | 2 | 302, 304 |
|   -8.570 | 6 | 300, 301, 302, 303, 304, 305 |
|   -8.185 | 1 | 302 |
|   -8.120 | 2 | 302, 304 |
|   -7.970 | 6 | 300, 301, 302, 303, 304, 305 |
|   -6.970 | 1 | 302 |
|   -6.371 | 1 | 304 |
|   -5.945 | 1 | 302 |
|   -4.730 | 1 | 302 |
|   -4.025 | 1 | 302 |
|   -4.010 | 6 | 300, 301, 302, 303, 304, 305 |
|   -2.810 | 1 | 302 |
|   -0.050 | 6 | 300, 301, 302, 303, 304, 305 |
|   +3.910 | 6 | 300, 301, 302, 303, 304, 305 |
|   +7.870 | 6 | 300, 301, 302, 303, 304, 305 |
|  +11.830 | 6 | 300, 301, 302, 303, 304, 305 |
|  +11.920 | 2 | 300, 304 |
|  +12.580 | 2 | 300, 303 |

### Verificacion del desfase de cada elevacion

El desfase `y_dibujo - cota` debe ser el MISMO para todas las cotas de una lamina.
Si lo es, la lectura de niveles esta verificada por dentro.

| Lamina | Desfase (m) | Dispersion (m) | Coherente | Cotas usadas | Descartadas |
|---|---:|---:|---|---:|---:|
| `2024_22-300` | 22.416 | 0.0000 | si | 17 | 0 |
| `2024_22-301` | 21.993 | 0.0000 | si | 9 | 0 |
| `2024_22-302` | 21.464 | 0.0000 | si | 17 | 9 |
| `2024_22-303` | 24.883 | 0.0000 | si | 20 | 20 |
| `2024_22-304` | 24.344 | 0.0000 | si | 22 | 4 |
| `2024_22-305` | 24.311 | 0.0000 | si | 17 | 17 |

## Registro de las plantas

Cada lamina se dibuja en su propio origen. Se corren todas al de `2024_22-101`
usando los ejes que comparten nombre. El residuo mide cuanto NO calzan
despues de correrlas: si es grande, algo esta mal leido.

| Lamina | Papel | dx (m) | dy (m) | Residuo (m) | Ejes usados |
|---|---|---:|---:|---:|---|
| `2024_22-100` | planta_fundaciones | +5.000 | +0.300 | 0.00003 | X: A,A',B,B',C,C',D,D',E',E1 / Y: 1,1',2,3,8A,8B |
| `2024_22-101` | planta_tipo | +0.000 | +0.000 | 0.00000 | X: A,A',B,B',C,C',D,D',E',E1 / Y: 1,1',1A',2,2A',3,8A,8B |
| `2024_22-102` | planta_cielo_4 | -0.000 | -3.200 | 0.00000 | X: A,A',B,C,C',D,D',E' / Y: 1,1',1A',2,2A',3 |

## Muros

Un muro se dibuja como sus dos caras. La **cobertura** es que porcentaje
del largo dibujado quedo emparejado: lo que falta es muro que el modelo
NO va a tener.

| Lamina | Muros | Cobertura | Caras sin pareja | Largo total (m) | Espesores (m) |
|---|---:|---:|---:|---:|---|
| `2024_22-100` | 9 | 98.5 % | 0 | 27.40 | 0.25×4, 0.30×3, 0.60×2 |
| `2024_22-101` | 9 | 98.5 % | 0 | 27.40 | 0.25×4, 0.30×3, 0.60×2 |
| `2024_22-102` | 8 | 97.8 % | 0 | 24.72 | 0.25×3, 0.30×3, 0.60×2 |

## Pilares

| Lamina | Pilares | Grupos | Secciones | Contorno abierto | No rectangulares | Etiqueta no calza |
|---|---:|---:|---|---:|---:|---:|
| `2024_22-100` | 7 | 8 | 0.70x0.70×7 | 1 | 1 | 7 |
| `2024_22-101` | 8 | 8 | 0.70x0.70×8 | 1 | 0 | 0 |
| `2024_22-102` | 8 | 8 | 0.70x0.70×8 | 0 | 0 | 1 |

## Vigas

El **ancho** se mide del dibujo; el **alto** se lee de la etiqueta
(`V. 60/80` = 60 de ancho x 80 de alto). Que el ancho medido calce con
el rotulo es una verificacion cruzada: las dos cifras vienen de fuentes
distintas del plano.

| Lamina | Vigas | Cobertura | Con etiqueta | Sin alto | Ancho no calza | Secciones |
|---|---:|---:|---:|---:|---:|---|
| `2024_22-100` | 7 | 98.8 % | 7 | 0 | 0 | 0.20/1.20×1, 0.20/1.60×3, 0.20/1.80×3 |
| `2024_22-101` | 12 | 97.7 % | 12 | 0 | 0 | 0.30/0.80×2, 0.40/0.80×1, 0.60/0.80×9 |
| `2024_22-102` | 12 | 97.6 % | 12 | 0 | 0 | 0.30/0.80×2, 0.40/0.80×1, 0.60/0.80×9 |

## Losa

El espesor de losa no se puede medir en planta: se lee del atributo
`ESP` del bloque `losa-ne`, que tiene nombre y por lo tanto no hay que
adivinar cual de los numeros del plano es.

| Panos rotulados | Espesores (m) | Espesor unico | Rotulos ilegibles |
|---:|---|---|---:|
| 22 | 0.15×22 | si | 0 |

## Material

Hormigon **G35_10**, f'c = **35 MPa**, gamma = 25 kN/m3.

> Nota de la lamina 2024_22-100 (PLANTA FUNDACIONES): 'HORMIGON G35_10: (Desde fundaciones A Cielo piso 4) - RESISTENCIA A COMPRESION PROBETA CILINDRICA FC' = 35 MPA, EQUIVALENTE A RESISTENCIA A COMPRESION PROBETA CUBICA R28 = 40 MPA'. El G20_10 que tambien aparece es para el radier armado, no estructural.

## Lo que quedo dudoso

- `2024_22-100`: ejes rotulados sin linea de eje que los respalde: ["E'"]
- `2024_22-100`: 1 grupos de la capa de pilares que no son rectangulos
- `2024_22-100`: 7 pilares donde la etiqueta no calza con lo medido
- `2024_22-101`: ejes rotulados sin linea de eje que los respalde: ["E'"]
- `2024_22-102`: ejes rotulados sin linea de eje que los respalde: ["E'"]
- `2024_22-102`: 1 pilares donde la etiqueta no calza con lo medido

> Esto es una lectura del plano, no una interpretacion estructural.
> Los puntos dudosos hay que resolverlos MIRANDO el plano: la geometria
> sola no alcanza para decidirlos.

