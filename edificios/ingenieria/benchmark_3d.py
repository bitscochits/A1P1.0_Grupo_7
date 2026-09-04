#!/usr/bin/env python3
"""
3D OpenSeesPy Model: Edificio de Ingenieria - Universidad de los Andes
Benchmark structural model for computational methods course.
"""

import openseespy.opensees as ops
import json
import math
import os
import sys

# La fisica compartida (torsion de Saint-Venant, reparto tributario)
# vive en benchmark/modelo_benchmark.py: una sola definicion para todo
# el proyecto. Se agrega esa carpeta a sys.path porque los edificios y
# el benchmark ya no comparten carpeta.
_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_RAIZ, 'benchmark'))
sys.path.insert(0, os.path.join(_RAIZ, 'comun'))

import modelo_benchmark as mb            # noqa: E402

# =============================================================================
# GEOMETRY DATA
# =============================================================================
X_axes = [8.02, 11.32, 14.72, 18.02, 28.02, 38.02, 48.02, 53.02, 55.57, 58.02]
#         E      Ea     Ed     F      G      H      I      I'    Jm      J
#
# El eje J (58.021) sale de las plantas -102 y -103, y solo existe en
# los pisos 3o y 4o. Ahi no hay pilares de hormigon: la estructura es
# METALICA (ver ACERO mas abajo).
#
# 'Jm' (55.57) es el PILAR DEL MEDIO del voladizo metalico. No tiene
# globo propio en el plano, pero las plantas -102 y -103 traen una
# viga en Y sobre X = 55.571, y ahi converge el arriostramiento.

# Ejes Y, capa RLE-EJE del plano 2017_67-100 (fundaciones). Cada eje se
# identifica por su GLOBO (un CIRCLE de r=0.438 m en el margen de la
# lamina) y la etiqueta MTEXT que cae dentro.
#
# CUIDADO: el globo NO siempre esta sobre su linea de eje. Cuando dos
# ejes quedan a menos de un diametro (aca hay pares a 0.25 m), el
# dibujante corre el globo y lo une a su eje con un QUIEBRE: un tramo
# corto horizontal desde el globo y luego un tramo vertical hasta la
# linea larga. Hay que seguir ese quiebre; leer la altura del globo da
# la coordenada equivocada.
#
#   eje   globo      eje real    como se lee
#   3'    46.925  -> 47.701      quiebre de 0.78 m
#   3     47.951     47.951      directo
#   2a    50.256     50.256      directo
#   2     55.201     55.201      directo
#   1''   60.201     60.201      directo
#   1     63.117  -> 64.101      quiebre
#   1'    64.154  -> 64.351      quiebre
#   1b    65.221  -> 64.651      quiebre de 0.57 m
#   8     72.751     72.751      directo
#
# Verificado en las 4 laminas de planta (-100, -101, -102, -103): la
# grilla relativa al eje 3 es identica en todas (0, 2.305, 7.250,
# 12.250, 16.150 m), aunque cada lamina esta insertada en un origen
# distinto. Los muros de la capa RLE-MURO caen sobre los ejes
# corregidos y no sobre los globos: el muro del eje 3-3' ocupa la
# banda Y 47.60-47.90 (contiene 47.701, no 46.92) y el del eje 1b la
# banda 64.55-64.85 (contiene 64.651, no 65.22).
# El primer valor NO es un eje de la grilla original: es el borde del
# VOLADIZO sur, donde mueren las vigas que pasan del eje 3. Existe solo
# en los pisos altos y solo entre dos ejes X (ver VOLADIZO_SUR).
Y_axes = [43.83, 47.70, 50.26, 55.20, 60.20, 64.65, 72.75]
#         volad. 3'     2a     2      1''    1b     8

# Cotas de losa reales, leidas de los titulos de las plantas
# (capa RLA-TEXTOS2) y de las cotas que los acompannan:
#
#   -100  planta fundaciones            -7.97
#   -101  planta cielo 1o subterraneo   -4.01
#   -101  planta cielo piso 1o          -0.05
#   -102  planta cielo piso 2o          +3.91
#   -102  planta cielo piso 3o          +7.87
#   -103  planta cielo piso 4o         +11.83
#
# Pisos uniformes de 3.96 m. Lo confirman por separado las marcas de
# nivel de la elevacion 2017_67-300 (13.79, 17.75, 21.71, 25.67, 29.63,
# 33.59 en la lamina: diferencias de 3.96 exactas) y sus rotulos de
# piso 1oS, 1o, 2o, 3o, 4o. Las laminas -2xx son armaduras de estas
# mismas plantas: no existen pisos 5o a 8o.
#
# Antes el modelo tenia 9 niveles hasta +28.5 m con pisos de 3.5 m.
# El modelo trabaja con la base en z = 0; la cota real es
# COTA_BASE + heights[lev].
COTA_BASE = -7.97
heights = [0.0, 3.96, 7.92, 11.88, 15.84, 19.80]

# LA PLANTA SE ACHICA HACIA ARRIBA. El edificio no es un prisma: por
# el norte termina en el eje 1/1b y la franja hasta el eje 8 existe
# solo en el subterraneo.
#
# Contado sobre las plantas, vigas a menos de 0.7 m de cada eje Y:
#
#   eje              3'    2a     2    1''    1b     8
#   1o subterraneo    -     -     1     -     10    19
#   piso 1o          19     9    26    10      4     -
#   piso 2o          20    10    27    10      5     -
#   piso 3o          22    11    32    12      6     -
#   piso 4o          20    10    32    12      6     -
#
# Del piso 1o hacia arriba el eje 8 no tiene NADA. El modelo lo ponia
# en los cinco pisos: una franja de 8.10 x 45 m = 364 m2 por piso, en
# cuatro niveles, de losa, vigas y columnas que no existen.
#
# IY_MAX[lev] = ultimo indice de Y_axes que existe en ese nivel.
# (Los indices subieron 1 al anteponer el eje del voladizo sur.)
IY_MAX = {0: 6, 1: 6, 2: 5, 3: 5, 4: 5, 5: 5}

# VOLADIZO SUR (Y = 43.83). Las vigas pasan del eje 3 y mueren en el
# aire; no hay pilar que las reciba. No cruza toda la planta y ademas
# CAMBIA DE SITIO segun el piso, leido de las plantas -102 y -103:
#
#   piso 2o (+3.91)   viga en Y=43.831 de X 18.32 a 25.21   -> entre F y G
#   piso 3o (+7.87)   viga en Y=43.831 de X 28.32 a 37.72   -> entre G y H
#   piso 4o (+11.83)  idem
#
# VOLADIZO_SUR[lev] = (ix desde, ix hasta) donde existe el eje 0.
#
# El del PISO 2o (nivel 3, entre F y G) se saco: no corresponde a un
# balcon del edificio. Las vigas que el DXF muestra ahi en Y = 43.831
# son de otra cosa. Quedan los de los pisos 3o y 4o, entre G y H.
IDX_VOLADIZO_SUR = 0
VOLADIZO_SUR = {4: (4, 5), 5: (4, 5)}

# EJE J y su pilar intermedio: la franja metalica del oriente, solo en
# los pisos 3o y 4o.
IDX_EJE_J = len(X_axes) - 1          # 58.02
IDX_PILAR_MEDIO = len(X_axes) - 2    # 55.57
NIVELES_EJE_J = (4, 5)


# UN EJE DE LA GRILLA NO IMPLICA UN PILAR. Contrastando la capa
# RLE-PILAR de las plantas contra la grilla, el plano tiene 18 pilares
# por piso y el modelo ponia 40: sobraban 115 de 190, el 61%, con
# 2846 kN de peso propio inventado.
#
#   ejes X CON pilar : E, F, G, H, I, I'
#          SIN pilar : Ea (11.32) y Ed (14.72)  <- caras del nucleo:
#                      ahi lo que hay son MUROS
#   ejes Y CON pilar : 3 (47.95), 2 (55.20), 1 (64.10)
#          SIN pilar : 2a (50.26) y 1'' (60.20) <- ejes de muro y de
#                      referencia
#
# Los ejes se QUEDAN en la grilla aunque no lleven pilar, porque de
# ellos cuelgan dos cosas: las vigas, y los brazos rigidos con que los
# muros se atan al marco. Sacarlos dejaba 13 de 25 muros sin ningun
# nudo a menos de 4 m -- los cuatro del nucleo entre 4.65 y 5.29 m --,
# o sea el nucleo desconectado.
IX_SIN_PILAR = {1, 2}        # Ea, Ed
IY_SIN_PILAR = {2, 4}        # 2a, 1''


def hay_pilar(ix, iy):
    """Si en ese cruce de la grilla el plano dibuja un pilar."""
    return ix not in IX_SIN_PILAR and iy not in IY_SIN_PILAR


def es_metalico(ix):
    """Si el eje pertenece al voladizo metalico del oriente."""
    return ix >= IDX_PILAR_MEDIO


def columna_metalica(ix, iy):
    """
    Si la COLUMNA en (ix, iy) es de acero.

    Lo son las del voladizo metalico del oriente y tambien las de los
    BALCONES del sur: el balcon se apoya en pilares de acero, aunque
    sus vigas sean de hormigon. Por eso no basta con mirar el eje X.
    """
    return es_metalico(ix) or iy == IDX_VOLADIZO_SUR

# LA FUNDACION ES ESCALONADA. La elevacion 2017_67-300 (eje 1-1')
# rotula los pilares tramo por tramo, y el mas bajo tiene solo TRES:
#
#   -7.97 -> -4.01   (3)  E, F, G
#   -4.01 -> -0.05   (6)  E, F, G, H, I, I'
#   -0.05 -> +3.91   (6)  ...
#   +3.91 -> +7.87   (6)
#   +7.87 -> +11.83  (6)
#
# Los ejes H, I e I' NO bajan a la fundacion profunda: se fundan en
# -4.01. Concuerda con los dos N.R. de la planta de fundaciones
# (-7.97 y -4.01) y con los ocho muros del oriente, que ya arrancaban
# en el nivel 1.
#
# IX_MIN_BASE = primer indice de X_axes que llega a la base. Los
# anteriores arrancan en el nivel 1.
#   X_axes = 8.02  11.32  14.72  18.02  28.02  38.02  48.02  53.02
#   ejes      E     Ea     Ed     F      G      H      I      I'
IX_DESDE_NIVEL1 = 5      # H en adelante


def pano_existe(ix, iy, lev):
    """
    Si el pano de losa (ix, iy) existe en ese nivel.

    Hacen falta sus CUATRO esquinas, no dos: con el voladizo sur, que
    termina en mitad de la grilla, mirar solo dos esquinas da por
    bueno un pano cuyas vigas no se crearon.
    """
    return all(existe(a, b, lev)
               for a in (ix, ix + 1) for b in (iy, iy + 1))


def existe(ix, iy, lev):
    """Si el nudo de grilla (ix, iy) existe en ese nivel."""
    if iy > IY_MAX[lev]:
        return False
    if iy == IDX_VOLADIZO_SUR:
        # El voladizo sur solo existe en su tramo de X y en su piso.
        r = VOLADIZO_SUR.get(lev)
        return r is not None and r[0] <= ix <= r[1]
    if es_metalico(ix):
        return lev in NIVELES_EJE_J
    if lev == 0 and ix >= IX_DESDE_NIVEL1:
        return False          # el oriente se funda en -4.01
    return True


nX = len(X_axes)
nY = len(Y_axes)
nLevels = len(heights)
nNodesPerFloor = nX * nY

# =============================================================================
# MATERIAL AND SECTION DATA
# =============================================================================
fpc = 28.0
Ec = 4700.0 * math.sqrt(fpc) * 1000.0  # Convert MPa -> kPa for m/kN units
Gc = Ec / (2.0 * (1.0 + 0.2))

col_b, col_h = 0.50, 0.50
beamX_b, beamX_h = 0.30, 0.60
beamY_b, beamY_h = 0.30, 0.80
slab_t = 0.25
gamma = 25.0

A_col = col_b * col_h
Iy_col = col_b * col_h**3 / 12.0
Iz_col = col_h * col_b**3 / 12.0
# Saint-Venant, no el min(Iy,Iz)*0.3 de antes: esa expresion no
# corresponde a ninguna formula y subestimaba J entre 5.6 y 10.2 veces.
# En un edificio de 6 niveles con planta irregular y sismo EX/EY la
# rigidez torsional si carga las columnas.
J_col = mb.J_rectangular(col_b, col_h)

# CONVENCION DE NOMBRES DE LAS INERCIAS DE VIGA. Es la misma de
# modelo_benchmark.py y la que espera el servidor:
#
#     Iz_vig = GRAVEDAD  (b*h^3/12, la del canto: flexion vertical)
#     Iy_vig = LATERAL   (h*b^3/12)
#
# Y en la llamada 'element' van CRUZADAS, porque con vecxz=(0,0,1) el
# eje local z queda vertical y la flexion por gravedad ocurre alrededor
# del eje local y:  element(..., Iz_vig, Iy_vig, transf).
#
# Estos nombres estaban al reves en este archivo. El modelo local salia
# bien igual -porque la llamada 'element' tambien estaba al reves y los
# dos errores se cancelaban- pero el JSON exportado sale con los
# nombres del CONTRATO, y el servidor los cruzaba segun la convencion
# buena: le metia la inercia debil (0.00135) donde va la de gravedad
# (0.0054). O sea que benchmark_3d.py y el servidor NO calculaban el
# mismo modelo: 0.22 mm de diferencia, un 4% del descenso maximo.
#
# El round-trip no lo veia porque comparaba solo REACCIONES, y esas son
# iguales por estatica pase lo que pase con la rigidez. Ahora tambien
# compara desplazamientos.
A_beamX = beamX_b * beamX_h
Iz_beamX = beamX_b * beamX_h**3 / 12.0   # gravedad (canto 0.60)
Iy_beamX = beamX_h * beamX_b**3 / 12.0   # lateral
J_beamX = mb.J_rectangular(beamX_b, beamX_h)

A_beamY = beamY_b * beamY_h
Iz_beamY = beamY_b * beamY_h**3 / 12.0   # gravedad (canto 0.80)
Iy_beamY = beamY_h * beamY_b**3 / 12.0   # lateral
J_beamY = mb.J_rectangular(beamY_b, beamY_h)

# BRAZO RIGIDO viga-muro. No es un elemento real: representa la parte
# del muro que va desde su EJE hasta la cara donde llega la viga.
#
# Se modela como BARRA muy rigida y no con rigidLink, porque los nodos
# de piso ya son esclavos del diafragma: hacerlos ademas esclavos de un
# vinculo rigido deja dos restricciones peleando por los mismos GDL y
# OpenSees devuelve una matriz inconsistente.
#
# x100 alcanza de sobra para que se comporte como rigido sin arruinar
# el condicionamiento numerico (x1e6 lo haria).
# Hasta donde puede estirarse un brazo para buscar nudo de marco. Un
# brazo mucho mas largo que eso ya no representa el muro sino que
# inventa una viga rigida que no existe.
DIST_MAX_BRAZO = 4.0

FACTOR_BRAZO = 100.0
A_brazo = A_col * FACTOR_BRAZO
I_brazo = Iy_col * FACTOR_BRAZO
J_brazo = J_col * FACTOR_BRAZO

# ================================================================
# ACERO: el voladizo metalico del oriente (entre los ejes I' y J)
# ================================================================
# La elevacion 2017_67-300 lo rotula entero:
#   P.M. 300x300x20   pilares, tubo cuadrado de 300 mm y 20 de pared
#   V.M. 300x300x5    vigas,   tubo cuadrado de 300 mm y 5 de pared
#   y 8 lineas en cruz -> arriostramiento de San Andres
#   "VER DETALLE CONEXION MET. EN SERIE N 800"
#
# Solo existe en los pisos 3o y 4o, y ahi NO hay pilares de hormigon
# mas alla del eje I': eso lo confirma la planta, que en esa franja no
# trae nada en RLE-PILAR.
E_acero = 200.0e6            # kPa (200 GPa)
G_acero = E_acero / (2.0 * (1.0 + 0.3))
gamma_acero = 78.5           # kN/m3


def props_tubo(b, t):
    """
    (A, I, J) de un tubo cuadrado de lado b y pared t, en m.

    La torsion es la de Bredt para seccion cerrada de pared delgada,
    J = 4*Am^2*t/p, NO la de Saint-Venant del rectangulo lleno: un
    tubo cerrado es much0 mas rigido a torsion que la suma de sus
    paredes.
    """
    bi = b - 2.0 * t
    A = b * b - bi * bi
    I = (b**4 - bi**4) / 12.0
    Am = (b - t) ** 2                 # area encerrada por la linea media
    per = 4.0 * (b - t)
    Jt = 4.0 * Am * Am * t / per
    return A, I, Jt


A_pm, I_pm, J_pm = props_tubo(0.30, 0.020)    # P.M. 300x300x20
A_vm, I_vm, J_vm = props_tubo(0.30, 0.005)    # V.M. 300x300x5

# Las diagonales del voladizo METALICO no vienen rotuladas. Se les da
# la misma seccion que las vigas metalicas, que es lo mas parecido que
# el plano ofrece. SUPUESTO, no dato.
A_dg, I_dg, J_dg = A_vm, I_vm, J_vm

# D.M. = DIAGONAL METALICA del voladizo de hormigon del sur. La
# elevacion 2017_67-306 (eje F-F') las rotula "D.M. %%C", donde %%C es
# el simbolo de diametro: son BARRAS REDONDAS, no tubos. Van dos, una
# por cada lado del voladizo, y miden 4.56 m.
#
# El diametro NO viene en el rotulo que se pudo leer. Se supone
# Ø 32 mm, que es un tirante razonable para colgar un voladizo de
# 4 m. SUPUESTO, no dato: cambiarlo aca.
DIAM_DM = 0.032
A_dm = math.pi * DIAM_DM**2 / 4.0
I_dm = math.pi * DIAM_DM**4 / 64.0
J_dm = 2.0 * I_dm                      # seccion circular llena

w_slab_dead = gamma * slab_t + 1.5  # 7.75 kN/m2
w_live_val = 2.0


# =============================================================================
# MUROS
# =============================================================================
# GEOMETRIA REAL, extraida del plano 2017_67-100 (fundaciones), capa
# RLE-MURO, leido con ezdxf. Las unidades del DXF son centimetros.
#
# Los ejes de ese plano coinciden al centimetro con los del modelo
# (E=8.021, Ea=11.321, Ed=14.721, F=18.021, G=28.021, H=38.021,
# I=48.021, I'=53.021), asi que las coordenadas de los muros estan en
# el mismo sistema y se usan directamente.
#
# Del DXF salieron 28 muros. Se descartaron 2 por quedar fuera de la
# planta modelada (llegan a Y=37.78 y Y=75.58; el modelo va de 47.70 a
# 72.75) y 3 por duplicados: el pareo de caras tomaba dos veces el
# mismo muro cuando habia caras a menos de 0.35 m.
#
# ESE FILTRO SE COMIO UN MURO DEL NUCLEO. En el nucleo de
# escalera/ascensor una misma cara sirve a DOS muros: la linea
# X = 14.621 es cara del muro de Y 50.36-51.84 y tambien del de
# Y 57.95-60.30. Al tratarla como duplicada se perdio el primero, y
# la caja del ascensor quedaba abierta por el lado oriente. Se
# reincorporo leyendo las caras crudas de RLE-MURO:
#
#   caras X = 14.621 y 14.871, de Y 50.356 a 51.835  ->  e = 0.25
#
# De paso se corrigio el muro en X = 11.57: estaba puesto en 11.29 con
# e = 0.25, y sus caras reales son 11.421 y 11.721, o sea e = 0.30.
#
# LA BANDA Y = 64.5 ES UNA JUNTA DE DILATACION, no un muro. Ahi los
# ejes 1 (64.101), 1' (64.351), 1AA (64.626) y 1b (64.651) van casi
# encima, y las caras de RLE-MURO se apilan asi:
#
#     64.251  cara exterior  |
#     64.451  cara interior  |  muro del eje 1', e = 0.20
#     ......  junta de 0.10 m
#     64.551  cara interior  |
#     64.751  cara exterior  |  muro del eje 1b, e = 0.20
#
# Un pareo automatico "el par mas ajustado primero" toma 64.451 con
# 64.551 y se inventa un muro de 10 cm que no existe: son las caras
# ENFRENTADAS de dos muros distintos, separadas por la junta. Las
# laminas -101 y -103 lo confirman con la capa "RLA-MURO INV DILATADO".
#
# Contrastando cada muro contra sus DOS caras, 20 de 24 calzaban al
# milimetro y los 4 que fallaban estaban todos en esta banda. Se
# corrigieron sus ejes y espesores, y aparecio un muro mas al otro
# lado de la junta (Y = 64.65, X 7.87-12.70, e = 0.20).
#
# Quedan 25 muros.
#
# CADA MURO SUBE SOLO HASTA DONDE LO MUESTRAN LAS PLANTAS. El sexto
# campo es la tupla de PISOS (1..5) en que el muro existe; el piso i va
# del nivel i-1 al i. Sale de contrastar cada muro contra la planta de
# cielo que corona cada piso, con verificar_planos.py:
#
#                       Fundac.  1o subt  piso 1o  piso 2o  piso 3o  piso 4o
#   losa (m)             -7.97    -4.01    -0.05    +3.91    +7.87   +11.83
#   largo presente (m)   168.3    105.0     78.8     13.1     13.1     13.1
#   % de los 168.3 m      100%      62%      47%       8%       8%       8%
#
# Antes el modelo ponia los 168.3 m en los 8 pisos. Sobre el nivel
# +-0.00 solo sobrevive el nucleo de escalera/ascensor (ejes Ea-Ed x
# 2a-1''): las mismas 12 corridas en los pisos 2o, 3o y 4o. Los
# 168.3 m de la fundacion incluyen los MUROS DE CONTENCION del
# subterraneo -- la lamina 2017_67-002 trae "disposicion de armaduras
# en muro contencion" --, que existen solo bajo tierra.
#
# Ocho muros del lado oriente (los de X 46.84 a 53.42 y los tramos en
# Y 64.30 a 70.33) aparecen recien en el piso 2o: el subterraneo no
# llega hasta alla. Se fundan en el nivel 1, no en la base. Es un
# apoyo real -- el plano de fundaciones les muestra zapata --, no un
# artificio: el edificio se funda escalonado.
#
# Los pisos de cada muro son siempre un tramo CONTIGUO; el modelo lo
# verifica al construir.
#
# Modelo: COLUMNA ANCHA. Cada muro es un elemento vertical en su
# centroide, con la seccion orientada por vecxz para que el eje fuerte
# quede en el plano del muro. Sus nodos entran al diafragma del piso.
#
# LIMITACION: sin brazos rigidos, las vigas que llegarian a las CARAS
# del muro se conectan a su eje.
#
# Formato: (direccion, coordenada fija, inicio, fin, espesor, pisos).
# Todo en metros; 'pisos' es la tupla de pisos 1..5 donde existe.
#   'Y' -> el muro corre en Y, sobre x = coordenada fija
#   'X' -> el muro corre en X, sobre y = coordenada fija
#        dir   fija    ini     fin   esp   pisos donde existe
MUROS = [
    ('X',  47.75,   8.02,  17.67, 0.30, (1,)),
    ('X',  50.26,  11.17,  14.87, 0.20, (1, 2, 3, 4, 5)),   # nucleo
    ('X',  60.20,  11.42,  14.62, 0.20, (1, 2, 3, 4, 5)),   # nucleo
    # El mismo muro del eje 1'' CRECE HACIA EL OESTE a partir del piso
    # 1o. En fundacion y 1o subterraneo va de 11.42 a 14.62, pero en
    # las plantas de cielo de los pisos 1o a 4o sus caras (Y = 60.101 y
    # 60.301) llegan hasta X = 7.671, con su remate en el extremo.
    # Como el tramo no existe en los dos niveles enterrados, va como
    # muro aparte y no alargando el anterior.
    ('X',  60.20,   7.67,  11.42, 0.20, (1, 2, 3, 4, 5)),
    ('X',  64.35,   8.37,  12.70, 0.20, (1,)),
    ('X',  64.35,  14.50,  18.37, 0.20, (1,)),
    ('X',  64.65,   7.87,  12.70, 0.20, (1,)),   # al otro lado de la junta
    ('X',  64.30,  37.67,  52.67, 0.30, (2,)),
    ('X',  64.70,  14.50,  29.27, 0.30, (1,)),
    ('X',  64.63,  41.77,  53.27, 0.15, (2,)),
    ('X',  67.67,  43.29,  46.92, 0.15, (2,)),
    ('X',  70.33,  43.29,  50.74, 0.15, (2,)),
    ('X',  72.76,  17.50,  29.57, 0.20, (1,)),
    ('Y',   7.77,  47.60,  55.55, 0.20, (1, 2)),
    # LOS MUROS TAMBIEN SE DIBUJAN COMO HATCH ROJO, no solo con las
    # lineas de RLE-MURO. Este tramo cierra el hueco entre los dos
    # muros del eje E y solo aparece achurado (capa RLA-HATCH2, patron
    # FP_2, color 1 = rojo), con el rotulo "M.H.A. e=20 (DILATADO)".
    ('Y',   7.77,  55.57,  57.93, 0.20, (1,)),
    ('Y',   7.77,  57.95,  63.75, 0.20, (1,)),
    ('Y',   7.77,  64.55,  72.75, 0.20, (1,)),
    ('Y',  11.29,  50.16,  51.84, 0.25, (1, 2, 3, 4, 5)),   # nucleo
    ('Y',  11.57,  57.95,  60.30, 0.30, (1, 2, 3, 4, 5)),   # nucleo
    ('Y',  14.47,  57.95,  60.30, 0.30, (1, 2, 3, 4, 5)),   # nucleo
    ('Y',  14.75,  50.36,  51.84, 0.25, (1, 2, 3, 4, 5)),   # nucleo
    ('Y',  18.22,  47.60,  64.45, 0.30, (1,)),
    ('Y',  29.42,  64.55,  72.75, 0.30, (1,)),
    ('Y',  46.84,  64.70,  67.75, 0.15, (2,)),
    ('Y',  48.17,  48.30,  54.85, 0.30, (2,)),
    ('Y',  48.17,  55.55,  63.75, 0.30, (2,)),
    ('Y',  53.42,  64.55,  72.75, 0.30, (2,)),
]


def props_muro(largo, espesor):
    """
    Seccion rectangular del muro: espesor x largo.
    El eje FUERTE es el que flecta en el plano del muro; va en la
    casilla Iy, que es la que resiste segun el vecxz que se le asigna.
    """
    A = espesor * largo
    I_fuerte = espesor * largo**3 / 12.0
    I_debil = largo * espesor**3 / 12.0
    J = mb.J_rectangular(espesor, largo)
    return A, I_fuerte, I_debil, J


# Mapas de vigas por posicion en la grilla, llenados por build_model().
WALL = {}          # (indice de muro, nivel) -> tag del elemento
WALL_NODES = {}    # (indice de muro, nivel) -> tag del nodo
MUROS_PROPS = {}   # indice de muro -> (dir, largo, A, Iy, Iz, J)
XBEAM = {}   # (nivel, ix, iy) -> viga en X entre los ejes ix e ix+1
YBEAM = {}   # (nivel, ix, iy) -> viga en Y entre los ejes iy e iy+1


def build_model():
    """Build the full model: nodes, elements, constraints, analysis settings."""
    ops.wipe()
    ops.model('basic', '-ndm', 3, '-ndf', 6)

    # Material
    ops.uniaxialMaterial('Elastic', 1, Ec)

    # Geometric transformations
    ops.geomTransf('Linear', 1, 1, 0, 0)
    ops.geomTransf('Linear', 2, 0, 0, 1)
    ops.geomTransf('Linear', 3, 0, 0, 1)
    # Muros: elementos VERTICALES. vecxz apunta a lo largo del muro, de
    # modo que su inercia fuerte (que va en la casilla Iy) resista la
    # flexion en el plano del muro.
    ops.geomTransf('Linear', 4, 1, 0, 0)   # muros que corren en X
    ops.geomTransf('Linear', 5, 0, 1, 0)   # muros que corren en Y

    # Nodes
    node_coords = {}
    nid = 1
    # La numeracion se mantiene aunque falten nodos: se dejan HUECOS
    # en los ids en vez de renumerar. OpenSees acepta ids no
    # consecutivos, y asi la formula lev*nNodesPerFloor + ix*nY + iy + 1
    # sigue valiendo en todo el resto del archivo.
    for lev in range(nLevels):
        z = heights[lev]
        for ix in range(nX):
            for iy in range(nY):
                if existe(ix, iy, lev):
                    node_coords[nid] = (X_axes[ix], Y_axes[iy], z)
                    ops.node(nid, X_axes[ix], Y_axes[iy], z)
                nid += 1

    # Fixed supports at level 0
    for i in range(1, nNodesPerFloor + 1):
        if i in node_coords:
            ops.fix(i, 1, 1, 1, 1, 1, 1)

    # Elements
    elem_counter = 1
    col_list = []
    xbeam_list = []
    ybeam_list = []
    colmet_list = []      # pilares de acero (balcones y eje J)
    diag_list = []        # V invertida del voladizo metalico (tubo)
    dm_list = []          # D.M. del voladizo sur (barra redonda)
    # Mapas (nivel, ix, iy) -> tag. Sin esto no se puede saber que
    # elemento borda cada pano de losa al repartir la carga.
    XBEAM.clear()
    YBEAM.clear()

    # Columns
    for lev in range(nLevels - 1):
        for ix in range(nX):
            for iy in range(nY):
                if not (existe(ix, iy, lev) and existe(ix, iy, lev + 1)):
                    continue
                if not hay_pilar(ix, iy):
                    continue        # ese eje no lleva columna
                bot = lev * nNodesPerFloor + ix * nY + iy + 1
                top = (lev + 1) * nNodesPerFloor + ix * nY + iy + 1
                if columna_metalica(ix, iy):
                    # P.M. 300x300x20, tubo de acero.
                    ops.element('elasticBeamColumn', elem_counter, bot, top,
                                A_pm, E_acero, G_acero, J_pm, I_pm, I_pm, 1)
                    colmet_list.append(elem_counter)
                else:
                    ops.element('elasticBeamColumn', elem_counter, bot, top,
                                A_col, Ec, Gc, J_col, Iy_col, Iz_col, 1)
                    col_list.append(elem_counter)
                elem_counter += 1

    # X-beams
    for lev in range(1, nLevels):
        for ix in range(nX - 1):
            for iy in range(nY):
                if not (existe(ix, iy, lev) and existe(ix + 1, iy, lev)):
                    continue
                n1 = lev * nNodesPerFloor + ix * nY + iy + 1
                n2 = lev * nNodesPerFloor + (ix + 1) * nY + iy + 1
                # Las vigas de los balcones son de HORMIGON, como las
                # del resto del edificio. Solo los pilares del borde y
                # las diagonales son de acero.
                ops.element('elasticBeamColumn', elem_counter, n1, n2,
                            A_beamX, Ec, Gc, J_beamX, Iz_beamX, Iy_beamX, 2)
                xbeam_list.append(elem_counter)
                XBEAM[(lev, ix, iy)] = elem_counter
                elem_counter += 1

    # Y-beams
    for lev in range(1, nLevels):
        for ix in range(nX):
            for iy in range(nY - 1):
                if not (existe(ix, iy, lev) and existe(ix, iy + 1, lev)):
                    continue
                n1 = lev * nNodesPerFloor + ix * nY + iy + 1
                n2 = lev * nNodesPerFloor + ix * nY + (iy + 1) + 1
                ops.element('elasticBeamColumn', elem_counter, n1, n2,
                            A_beamY, Ec, Gc, J_beamY, Iz_beamY, Iy_beamY, 3)
                ybeam_list.append(elem_counter)
                YBEAM[(lev, ix, iy)] = elem_counter
                elem_counter += 1

    # -------------------------------------------------------------
    # DIAFRAGMAS RIGIDOS
    # -------------------------------------------------------------
    # Antes esto era:
    #     ops.equalDOF(master, slave, 1, 2, 6)
    # que NO es un diafragma: obliga a que todos los nodos tengan el
    # MISMO ux, uy y rz, o sea que el piso solo puede trasladarse y
    # nunca rotar. En una planta irregular bajo sismo la torsion es
    # justo lo que hay que capturar, y quedaba eliminada.
    #
    # Un diafragma rigido deja el piso moverse como CUERPO RIGIDO en su
    # plano, rotacion incluida:
    #     ux_i = ux_m - rz*(y_i - y_m)
    #     uy_i = uy_m + rz*(x_i - x_m)
    #     rz_i = rz_m           <- esto si es comun a todos
    #
    # El nodo maestro va en el CENTRO GEOMETRICO del piso, que es donde
    # se aplica el corte sismico. Necesita constraints('Transformation').
    # -------------------------------------------------------------
    # MUROS (columna ancha)
    # -------------------------------------------------------------
    wall_list = []
    brazo_list = []
    brazos_hechos = set()
    wall_nodes = {}          # (indice de muro, nivel) -> nodo
    WALL_NODES.clear()       # copia a nivel de modulo, para apply_gravity
    nid_muro = nLevels * nNodesPerFloor + 1

    for im, (dirn, fija, ini_w, fin_w, esp, pisos) in enumerate(MUROS):
        largo = fin_w - ini_w
        if dirn == 'X':
            xw = (ini_w + fin_w) / 2.0
            yw = fija
            transf_muro = 4
        else:
            xw = fija
            yw = (ini_w + fin_w) / 2.0
            transf_muro = 5

        A_w, Iy_w, Iz_w, J_w = props_muro(largo, esp)
        MUROS_PROPS[im] = (dirn, largo, A_w, Iy_w, Iz_w, J_w)

        # El muro ocupa los pisos 'pisos', que tienen que ser un tramo
        # contiguo: si no, quedaria un nodo colgado sin elemento arriba
        # ni abajo y la matriz sale singular.
        pisos = sorted(pisos)
        if pisos != list(range(pisos[0], pisos[-1] + 1)):
            raise ValueError(f"muro {im}: los pisos {pisos} no son contiguos")
        if pisos[-1] > nLevels - 1:
            raise ValueError(f"muro {im}: piso {pisos[-1]} fuera de {nLevels-1}")

        # Nodos del nivel de fundacion del muro hasta su coronacion.
        lev_base, lev_tope = pisos[0] - 1, pisos[-1]
        for lev in range(lev_base, lev_tope + 1):
            ops.node(nid_muro, xw, yw, heights[lev])
            node_coords[nid_muro] = (xw, yw, heights[lev])
            wall_nodes[(im, lev)] = nid_muro
            WALL_NODES[(im, lev)] = nid_muro
            nid_muro += 1

        # Apoyo en el nivel donde el muro arranca.
        #
        # En la base (nivel 0) no hay diafragma: empotramiento completo,
        # como siempre.
        #
        # Arriba de la base hay que tener cuidado. El nodo ya es esclavo
        # del diafragma de ese piso, que le ata los DOF EN el plano
        # (ux, uy, rz). Empotrarlo del todo ataria tambien esos tres y,
        # como el diafragma es rigido, dejaria INMOVIL TODO EL PISO: la
        # deriva del piso 1 se iria a cero y los 105 m de muro de ese
        # piso quedarian de adorno.
        #
        # Se restringen entonces solo los DOF que el diafragma NO toca
        # (uz, rx, ry) -- el mismo recurso que se usa con los nodos
        # maestros. Fisicamente: el muro se apoya en vertical sobre el
        # piso de abajo y se mueve en horizontal con el.
        #
        # Lo que queda fuera del modelo es el empotramiento LATERAL de
        # la fundacion escalonada del oriente. Con diafragma rigido no
        # hay como ponerlo sin congelar el piso entero.
        if lev_base == 0:
            ops.fix(wall_nodes[(im, lev_base)], 1, 1, 1, 1, 1, 1)
        else:
            ops.fix(wall_nodes[(im, lev_base)], 0, 0, 1, 1, 1, 0)

        for lev in range(lev_base, lev_tope):
            ops.element('elasticBeamColumn', elem_counter,
                        wall_nodes[(im, lev)], wall_nodes[(im, lev + 1)],
                        A_w, Ec, Gc, J_w, Iy_w, Iz_w, transf_muro)
            WALL[(im, lev)] = elem_counter
            wall_list.append(elem_counter)
            elem_counter += 1

        # --- BRAZOS RIGIDOS viga-muro ---
        # Sin esto el muro solo esta atado al diafragma, que lo sujeta
        # EN EL PLANO (ux, uy, rz) y no en vertical. Bajo gravedad el
        # techo baja 2.42 mm y el remate del nucleo 0.20 mm: con la
        # deformada exagerada x300 son 725 mm contra 59 en pantalla, y
        # los muros se ven despegados del edificio.
        #
        # El brazo va del EJE del muro a los DOS nudos de marco mas
        # cercanos a ese eje, que es la distancia que en el edificio
        # real cubre el propio muro hasta la cara donde apoya la viga.
        # Es tambien lo que le da ancho: sin el, el muro se comporta
        # como si tuviera espesor cero.
        #
        # Se buscan por cercania AL EJE, no a los extremos del muro:
        # el brazo sale del eje, asi que esa es su longitud real.
        # Buscar por el extremo y medir desde el eje era incoherente y
        # dejaba sin brazo a muros que tenian un nudo a 50 cm.
        for lev in range(max(lev_base, 1), lev_tope + 1):
            # Solo los nudos que EXISTEN en ese nivel: la planta se
            # achica hacia arriba y el eje 8 no llega al piso 1o.
            cand = sorted(
                ((math.hypot(X_axes[i] - xw, Y_axes[j] - yw), i, j)
                 for i in range(nX) for j in range(nY)
                 if existe(i, j, lev)),
                key=lambda t: t[0])[:2]
            for dist, ix, iy in cand:
                if dist > DIST_MAX_BRAZO:
                    continue          # no hay marco cerca que agarrar
                nudo = lev * nNodesPerFloor + ix * nY + iy + 1
                nmuro = wall_nodes[(im, lev)]
                if (nmuro, nudo) in brazos_hechos:
                    continue
                brazos_hechos.add((nmuro, nudo))
                # El brazo es horizontal: mismas inercias cruzadas que
                # cualquier barra no vertical.
                ops.element('elasticBeamColumn', elem_counter,
                            nmuro, nudo,
                            A_brazo, Ec, Gc, J_brazo, I_brazo, I_brazo, 2)
                brazo_list.append(elem_counter)
                elem_counter += 1

    # --- ARRIOSTRAMIENTO del voladizo metalico ---
    # Es una V INVERTIDA (chevron), no una cruz de San Andres.
    #
    # La elevacion 2017_67-300 trae 8 lineas inclinadas, pero son solo
    # DOS diagonales: cada una va dibujada con sus dos caras, y cada
    # cara aparece duplicada. Y las dos SUBEN HACIA EL MISMO PUNTO:
    #
    #   izquierda  (49.76, 29.9) -> (51.80, 32.55)   sube a la derecha
    #   derecha    (54.16, 29.9) -> (52.12, 32.55)   sube a la izquierda
    #
    # Convergen arriba en el centro del vano, sobre el PILAR DEL MEDIO
    # (eje Jm). En una cruz de San Andres las diagonales se cruzarian
    # y llegarian a esquinas opuestas; aca llegan las dos al mismo
    # nudo alto. De ahi el nombre: V invertida.
    #
    # Van por LOS DOS LADOS del pilar del medio, o sea una por vano:
    # I' -> Jm  y  J -> Jm.
    # Solo en el vano que la elevacion muestra arriostrado: entre las
    # cotas +7.87 y +11.83, o sea el ultimo piso del voladizo. Poner
    # diagonales tambien en el piso de abajo seria inventarlas.
    for lev in NIVELES_EJE_J[1:]:
        for ix_pie in (IDX_PILAR_MEDIO - 1, IDX_EJE_J):
            for iy in range(nY):
                if not (existe(ix_pie, iy, lev - 1)
                        and existe(IDX_PILAR_MEDIO, iy, lev)):
                    continue
                pie = (lev - 1) * nNodesPerFloor + ix_pie * nY + iy + 1
                top = lev * nNodesPerFloor + IDX_PILAR_MEDIO * nY + iy + 1
                if pie not in node_coords or top not in node_coords:
                    continue
                ops.element('elasticBeamColumn', elem_counter, pie, top,
                            A_dg, E_acero, G_acero, J_dg, I_dg, I_dg, 2)
                diag_list.append(elem_counter)
                elem_counter += 1

    # --- DIAGONALES del voladizo de hormigon del sur ---
    # La elevacion 2017_67-306 (eje F-F') muestra dos "D.M." -- una a
    # cada lado del voladizo -- junto a los mismos P.M. y V.M. del
    # voladizo metalico. Miden 4.56 m y SUBEN hacia el eje 3.
    #
    # O sea que son TIRANTES: cuelgan la punta del voladizo del nudo
    # del nivel de arriba, en vez de apuntalarla desde abajo. Sin
    # ellos la punta queda en voladizo puro y baja mucho mas de lo
    # que baja en realidad.
    for lev, (ix_a, ix_b) in VOLADIZO_SUR.items():
        # SIEMPRE cuelga del nivel de ARRIBA. Si no hay nivel arriba,
        # ese balcon no lleva diagonal: se apoya en los pilares de
        # acero que suben desde el balcon de abajo.
        #
        # Colgarlo hacia abajo cuando falta el nivel superior parece
        # inofensivo, pero la diagonal queda en el MISMO vano que la
        # del piso de abajo y con la inclinacion opuesta: las dos
        # juntas forman una X, que es justo lo que el plano NO
        # muestra.
        lev_otro = lev + 1
        if lev_otro >= nLevels:
            continue
        for ix in (ix_a, ix_b):
            punta = lev * nNodesPerFloor + ix * nY + IDX_VOLADIZO_SUR + 1
            ancla = lev_otro * nNodesPerFloor + ix * nY + IDX_VOLADIZO_SUR + 2
            if punta not in node_coords or ancla not in node_coords:
                continue
            ops.element('elasticBeamColumn', elem_counter, punta, ancla,
                        A_dm, E_acero, G_acero, J_dm, I_dm, I_dm, 2)
            dm_list.append(elem_counter)
            elem_counter += 1

    # --- Fundacion del oriente, en el nivel 1 ---
    # Los ejes H, I e I' se fundan en -4.01, no en -7.97. Sin apoyo
    # ahi su nudo del nivel 1 no tiene NADA debajo y queda colgando de
    # las vigas: el primer intento dio 110 mm de descenso bajo peso
    # propio.
    #
    # Se restringen solo uz, rx y ry, que son los DOF que el diafragma
    # NO toca. Empotrarlos del todo ataria tambien ux, uy y rz y, como
    # el diafragma es rigido, dejaria inmovil el piso 1 entero. Es el
    # mismo recurso que ya se usa con los arranques de muro escalonados
    # y con los nodos maestros.
    apoyos_oriente = []
    for ix in range(IX_DESDE_NIVEL1, nX):
        for iy in range(nY):
            if not existe(ix, iy, 1):
                continue
            nid_o = 1 * nNodesPerFloor + ix * nY + iy + 1
            ops.fix(nid_o, 0, 0, 1, 1, 1, 0)
            apoyos_oriente.append(nid_o)

    xc = sum(X_axes) / nX
    yc = sum(Y_axes) / nY
    master_nodes = {}
    mid = nid_muro

    for lev in range(1, nLevels):
        ops.node(mid, xc, yc, heights[lev])
        node_coords[mid] = (xc, yc, heights[lev])
        master_nodes[lev] = mid

        esclavos = [lev * nNodesPerFloor + ix * nY + iy + 1
                    for ix in range(nX) for iy in range(nY)
                    if existe(ix, iy, lev)]
        # Los nodos de muro tambien pertenecen al diafragma del piso:
        # es lo que conecta el muro con el resto de la planta. Solo los
        # muros que llegan a este nivel tienen nodo aca.
        esclavos += [wall_nodes[(im, lev)] for im in range(len(MUROS))
                     if (im, lev) in wall_nodes]
        ops.rigidDiaphragm(3, mid, *esclavos)

        # El diafragma solo ata los DOF EN el plano (ux, uy, rz). Los de
        # fuera (uz, rx, ry) del maestro quedan sueltos y la matriz
        # saldria singular, porque el nodo no tiene ningun elemento.
        ops.fix(mid, 0, 0, 1, 1, 1, 0)
        mid += 1

    return (node_coords, col_list, xbeam_list, ybeam_list,
            master_nodes, wall_list, wall_nodes, brazo_list,
            apoyos_oriente, colmet_list, diag_list, dm_list)


def tributarias():
    """
    Reparte cada pano de losa a las 4 vigas que lo bordean, trazando
    bisectrices a 45 grados desde las esquinas.

        pano corto (b <= a)  -> la viga larga recibe un TRAPECIO
        pano largo  (b >  a) -> la viga corta recibe un TRIANGULO

    Una viga interior borda DOS panos, asi que acumula las dos
    contribuciones. Iterando por pano y sumando sus 4 aportes, la
    conservacion queda garantizada por construccion:
        sum(A_tributaria) == A_piso  por nivel

    Antes el reparto era 50/50 por franjas de media luz, que le da lo
    mismo a la viga larga que a la corta. En un pano 10x5 eso puede
    equivocar la carga de cada viga en decenas de por ciento.

    El area de piso NO es la misma en todos los niveles: la planta se
    achica hacia arriba (ver IY_MAX). Por eso se devuelve un
    diccionario {nivel: area}, no un solo numero.

    Devuelve (area_por_viga, A_por_nivel, detalle_panos).
    """
    area_por_viga = {}
    A_por_nivel = {lev: 0.0 for lev in range(1, nLevels)}
    detalle = []

    for ix in range(nX - 1):
        Lx = X_axes[ix + 1] - X_axes[ix]
        for iy in range(nY - 1):
            Ly = Y_axes[iy + 1] - Y_axes[iy]

            # Cada una de las 2 vigas en X recibe Ax; cada una de las 2
            # vigas en Y recibe Ay. Se cumple 2*Ax + 2*Ay == Lx*Ly.
            Ax = mb.area_tributaria_viga(Lx, Ly)
            Ay = mb.area_tributaria_viga(Ly, Lx)
            detalle.append({'ix': ix, 'iy': iy, 'Lx': Lx, 'Ly': Ly,
                            'A_pano': Lx * Ly, 'Ax': Ax, 'Ay': Ay,
                            'forma_x': 'trapecio' if Ly <= Lx else 'triangulo',
                            'forma_y': 'trapecio' if Lx <= Ly else 'triangulo'})

            for lev in range(1, nLevels):
                # El pano existe solo si existen sus cuatro bordes.
                if not pano_existe(ix, iy, lev):
                    continue
                A_por_nivel[lev] += Lx * Ly
                for t, A in ((XBEAM[(lev, ix, iy)], Ax),
                             (XBEAM[(lev, ix, iy + 1)], Ax),
                             (YBEAM[(lev, ix, iy)], Ay),
                             (YBEAM[(lev, ix + 1, iy)], Ay)):
                    area_por_viga[t] = area_por_viga.get(t, 0.0) + A

    return area_por_viga, A_por_nivel, detalle


def datos_vigas():
    """
    Devuelve {tag: (luz, direccion, area_seccion)} para todas las vigas.
    Se arma una vez; buscar linealmente en los mapas por cada viga seria
    O(n^2) sobre 656 vigas.
    """
    # La cuarta componente es el peso por metro. TODAS las vigas son
    # de hormigon, incluidas las de los balcones: de acero solo son
    # los pilares del borde y las diagonales.
    d = {}
    for (lev, ix, iy), t in XBEAM.items():
        d[t] = (X_axes[ix + 1] - X_axes[ix], 'X', A_beamX, gamma * A_beamX)
    for (lev, ix, iy), t in YBEAM.items():
        d[t] = (Y_axes[iy + 1] - Y_axes[iy], 'Y', A_beamY, gamma * A_beamY)
    return d


def apply_gravity(pattern_tag, use_self_weight, apply_live):
    """
    Aplica la carga de gravedad como DISTRIBUIDA sobre las vigas.

    Antes se aplicaba como dos fuerzas puntuales en los extremos
    (F = w*L/2 en cada nodo). La carga total se conservaba -por eso el
    equilibrio cerraba- pero las vigas NO flectaban por la losa: todo
    el momento del vano desaparecia. Para dimensionar vigas eso
    invalida el resultado.

    eleLoad -beamUniform con vecxz=(0,0,1) pone la gravedad en Wz local.
    """
    q = w_live_val if apply_live else w_slab_dead
    area_por_viga, _, _ = tributarias()
    vigas = datos_vigas()

    for tag, A in area_por_viga.items():
        L, _dir, A_sec, peso_m = vigas[tag]
        w = q * A / L                      # uniforme equivalente

        if use_self_weight and not apply_live:
            w += peso_m                    # peso propio (acero u hormigon)

        ops.eleLoad('-ele', tag, '-type', '-beamUniform', 0.0, -w, 0.0)

    # Peso propio de las columnas, como fuerzas nodales en sus extremos.
    if use_self_weight and not apply_live:
        for lev in range(nLevels - 1):
            h = heights[lev + 1] - heights[lev]
            for ix in range(nX):
                for iy in range(nY):
                    W = (gamma_acero * A_pm * h if columna_metalica(ix, iy)
                         else gamma * A_col * h)
                    # Solo donde la columna existe de verdad.
                    if not (existe(ix, iy, lev) and existe(ix, iy, lev + 1)
                            and hay_pilar(ix, iy)):
                        continue
                    n_bot = lev * nNodesPerFloor + ix * nY + iy + 1
                    n_top = (lev + 1) * nNodesPerFloor + ix * nY + iy + 1
                    ops.load(n_bot, 0.0, 0.0, -W / 2.0, 0.0, 0.0, 0.0)
                    ops.load(n_top, 0.0, 0.0, -W / 2.0, 0.0, 0.0, 0.0)

        # Peso propio de los MUROS, con el mismo esquema: mitad a cada
        # extremo de cada tramo. Hasta aca los muros no pesaban NADA
        # (ni en G ni en el peso sismico): unos 5-6% de la masa del
        # edificio no existia. Se veia en la deformada exagerada de
        # Unity: los remates del nucleo quedaban clavados a cota real,
        # flotando sobre un techo que bajaba a su alrededor, porque a
        # esos nodos no les llegaba ninguna carga vertical.
        for (im, lev), _tag in WALL.items():
            h = heights[lev + 1] - heights[lev]
            A_w = MUROS_PROPS[im][2]
            W = gamma * A_w * h
            ops.load(WALL_NODES[(im, lev)], 0.0, 0.0, -W / 2.0, 0.0, 0.0, 0.0)
            ops.load(WALL_NODES[(im, lev + 1)], 0.0, 0.0, -W / 2.0, 0.0, 0.0, 0.0)


# Coeficiente sismico pseudoestatico: corte basal como fraccion del
# peso sismico. Es un valor de trabajo, NO un calculo NCh433 completo
# (falta el espectro, el factor R, la zona y el tipo de suelo).
#
# El valor anterior era F = 10*nivel, o sea 360 kN de corte basal
# contra ~100.000 kN de peso: un coeficiente de 0.36%. Dos ordenes de
# magnitud por debajo de cualquier valor razonable en Chile, asi que
# los desplazamientos de EX/EY no representaban nada.
COEF_SISMICO = 0.10


def peso_sismico():
    """
    Peso por nivel: losa + terminaciones + peso propio de vigas y la
    mitad de columnas y muros de arriba y abajo. Se usa para repartir
    el corte basal en altura.

    Los muros no son iguales en todos los pisos, asi que su aporte se
    acumula tramo a tramo desde WALL. Antes no se incluian y el corte
    basal quedaba corto.
    """
    _, A_por_nivel, _ = tributarias()
    vigas = datos_vigas()

    W = {}
    for lev in range(1, nLevels):
        # Vigas, columnas y area de losa se cuentan POR NIVEL, porque
        # la planta se achica hacia arriba y antes se usaba el piso 1
        # para todos.
        tags_piso = ([XBEAM[k] for k in XBEAM if k[0] == lev]
                     + [YBEAM[k] for k in YBEAM if k[0] == lev])
        W_vigas_piso = sum(gamma * vigas[t][2] * vigas[t][0]
                           for t in tags_piso if t in vigas)

        n_col = sum(1 for ix in range(nX) for iy in range(nY)
                    if existe(ix, iy, lev) and hay_pilar(ix, iy))
        h_inf = heights[lev] - heights[lev - 1]
        h_sup = (heights[lev + 1] - heights[lev]) if lev < nLevels - 1 else 0.0
        W_col = gamma * A_col * n_col * (h_inf + h_sup) / 2.0

        # Mitad de cada tramo de muro que llega o sale de este nivel.
        # La mitad que va al nivel 0 se pierde en la base, igual que
        # en las columnas.
        W_mur = 0.0
        for (im, l), _tag in WALL.items():
            h_el = heights[l + 1] - heights[l]
            A_w = MUROS_PROPS[im][2]
            if l + 1 == lev or l == lev:
                W_mur += gamma * A_w * h_el / 2.0

        W[lev] = (w_slab_dead * A_por_nivel[lev] + W_vigas_piso
                  + W_col + W_mur)
    return W


def apply_lateral(direction):
    """
    Corte basal repartido en altura segun NCh433 simplificado:

        F_i = V * (W_i * h_i) / sum(W_j * h_j)

    Se aplica en el NODO MAESTRO de cada diafragma, que esta en el
    centro geometrico del piso. Antes se aplicaba en el nodo de esquina
    (ix=0, iy=0), lo que introduce una excentricidad artificial.
    """
    W = peso_sismico()
    V = COEF_SISMICO * sum(W.values())
    denom = sum(W[lev] * heights[lev] for lev in W)

    for lev in W:
        F = V * (W[lev] * heights[lev]) / denom
        nodo = master_nodes[lev]
        if direction == 'X':
            ops.load(nodo, F, 0.0, 0.0, 0.0, 0.0, 0.0)
        else:
            ops.load(nodo, 0.0, F, 0.0, 0.0, 0.0, 0.0)


def setup_analysis():
    # BandGeneral y Transformation: 'Plain' no sabe imponer un
    # rigidDiaphragm (su matriz de restriccion no es la identidad).
    ops.system('BandGeneral')
    ops.numberer('RCM')
    ops.constraints('Transformation')
    ops.integrator('LoadControl', 1.0)
    ops.algorithm('Linear')
    ops.analysis('Static')


# =============================================================================
# BUILD MODEL ONCE AND EXTRACT DATA
# =============================================================================
print("Building model...")
(node_coords, col_list, xbeam_list, ybeam_list,
 master_nodes, wall_list, wall_nodes, brazo_list,
 apoyos_oriente, colmet_list, diag_list, dm_list) = build_model()
total_nodes = len(node_coords)
nColumns = len(col_list)
nXbeams = len(xbeam_list)
nYbeams = len(ybeam_list)
nWalls = len(wall_list)
nBrazos = len(brazo_list)
nMetal = len(colmet_list) + len(diag_list) + len(dm_list)
nElements = nColumns + nXbeams + nYbeams + nWalls + nBrazos + nMetal
print(f"Nodes: {total_nodes}, Columns: {nColumns}, X-beams: {nXbeams}, Y-beams: {nYbeams}, Walls: {nWalls}, Brazos: {nBrazos}, "
      f"Acero: {len(colmet_list)} pilares + {len(diag_list)} Vinv + {len(dm_list)} DM, Total: {nElements}")
print("Constraints: fixed base + rigid diaphragm at all floors\n")

# Apoyos: los 48 de la base MAS el arranque de cada muro. Sin
# incluirlos, la suma de reacciones deja fuera lo que toman los muros y
# el chequeo de equilibrio de EX/EY falla por miles de kN.
#
# Ojo: el arranque no siempre esta en la base. Los ocho muros del
# oriente empiezan en el nivel 1 y ahi solo tienen restringidos uz, rx
# y ry (ver build_model), asi que aportan reaccion vertical pero no
# horizontal.
# Solo los nodos de base que EXISTEN: el oriente (ejes H, I, I') se
# funda en -4.01 y no tiene nudo en la cota -7.97.
# Solo los nodos de base que EXISTEN y que llevan pilar: un cruce sin
# pilar no tiene nada que apoyar.
support_nodes = [n for n in range(1, nNodesPerFloor + 1)
                 if n in node_coords
                 and hay_pilar((n - 1) // nY, (n - 1) % nY)]
apoyos_muro_sobre_base = []
for im, muro in enumerate(MUROS):
    lev_base = min(muro[5]) - 1
    support_nodes.append(wall_nodes[(im, lev_base)])
    if lev_base > 0:
        apoyos_muro_sobre_base.append(wall_nodes[(im, lev_base)])

# Los nudos del oriente fundados en -4.01 tambien son apoyos, y del
# mismo tipo: solo uz, rx y ry restringidos.
support_nodes += apoyos_oriente
apoyos_muro_sobre_base += apoyos_oriente


def run_load_case(name, load_func, **kwargs):
    """Rebuild model, apply loads, run analysis, return results."""
    ops.wipe()
    build_model()
    setup_analysis()

    ops.timeSeries('Linear', 1)
    ops.pattern('Plain', 1, 1)
    load_func(1, **kwargs)

    ok = ops.analyze(1)
    print(f"  {name}: Convergence {'OK' if ok == 0 else 'FAILED'}")

    ops.reactions()

    disp = {nid: [round(ops.nodeDisp(nid, i), 8) for i in range(1, 7)]
            for nid in node_coords}
    react = {nid: [round(ops.nodeReaction(nid, i), 4) for i in range(1, 7)]
             for nid in support_nodes}
    return disp, react


# =============================================================================
# RUN ALL LOAD CASES
# =============================================================================
results = {}
os.makedirs('results', exist_ok=True)

print("--- Running Load Cases ---")
results['G'] = dict(zip(['displacements', 'reactions'],
    run_load_case('G', apply_gravity, use_self_weight=True, apply_live=False)))
results['Q'] = dict(zip(['displacements', 'reactions'],
    run_load_case('Q', apply_gravity, use_self_weight=False, apply_live=True)))
results['EX'] = dict(zip(['displacements', 'reactions'],
    run_load_case('EX', lambda pt, **kw: apply_lateral('X'))))
results['EY'] = dict(zip(['displacements', 'reactions'],
    run_load_case('EY', lambda pt, **kw: apply_lateral('Y'))))

# =============================================================================
# ELEMENT FORCES (Representative Elements)
# =============================================================================
print("\n--- Extracting Element Forces ---")

rep_elems = {
    'col_bottom': (col_list[0], 'G'),
    'col_mid': (col_list[len(col_list) // 2], 'G'),
    'col_top': (col_list[-1], 'G'),
    'xbeam_first': (xbeam_list[0], 'G'),
    'xbeam_mid': (xbeam_list[len(xbeam_list) // 2], 'EX'),
    'ybeam_first': (ybeam_list[0], 'G'),
    'ybeam_mid': (ybeam_list[len(ybeam_list) // 2], 'EY'),
}

results['element_forces'] = {}
for label, (eid, lc) in rep_elems.items():
    ops.wipe()
    build_model()
    setup_analysis()
    ops.timeSeries('Linear', 1)
    ops.pattern('Plain', 1, 1)

    if lc in ('G',):
        apply_gravity(1, use_self_weight=True, apply_live=False)
    elif lc in ('Q',):
        apply_gravity(1, use_self_weight=False, apply_live=True)
    elif lc == 'EX':
        apply_lateral('X')
    elif lc == 'EY':
        apply_lateral('Y')

    ops.analyze(1)
    # eleResponse(..., 'localForce') entrega fuerzas en ejes LOCALES.
    # (ops.eleForce da ejes GLOBALES: en una columna el axial de gravedad
    #  aparece como cortante y la viga-Y parece no flectar. Ver reports/semana01.md §3.)
    forces = ops.eleResponse(eid, 'localForce')
    entry = {'element_id': eid, 'load_case': lc}
    if len(forces) >= 12:
        entry['i_end_local_N_Vy_Vz_T_My_Mz'] = [round(f, 4) for f in forces[:6]]
        entry['j_end_local_N_Vy_Vz_T_My_Mz'] = [round(f, 4) for f in forces[6:12]]
    results['element_forces'][label] = entry
    print(f"  {label}: elem {eid}, LC={lc}")

# =============================================================================
# EQUILIBRIUM CHECK
# =============================================================================
print("\n" + "=" * 60)
print("EQUILIBRIUM CHECK")
print("=" * 60)

total_G_applied = 0.0
total_Q_applied = 0.0

# Este conteo es INDEPENDIENTE del de apply_gravity: aqui se suma por
# geometria y alla se aplico elemento a elemento. Por eso hay que
# repetir aca la regla de que la planta se achica hacia arriba; si se
# olvidara, el chequeo de equilibrio acusaria una diferencia que no
# existe.
for lev in range(1, nLevels):
    for ix in range(nX - 1):
        dx = X_axes[ix + 1] - X_axes[ix]
        for iy in range(nY - 1):
            if not pano_existe(ix, iy, lev):
                continue
            dy = Y_axes[iy + 1] - Y_axes[iy]
            total_G_applied += w_slab_dead * dx * dy
            total_Q_applied += w_live_val * dx * dy

for lev in range(1, nLevels):
    for ix in range(nX - 1):
        dx = X_axes[ix + 1] - X_axes[ix]
        for iy in range(nY):
            if existe(ix, iy, lev) and existe(ix + 1, iy, lev):
                total_G_applied += gamma * beamX_b * beamX_h * dx
    for ix in range(nX):
        for iy in range(nY - 1):
            if not (existe(ix, iy, lev) and existe(ix, iy + 1, lev)):
                continue
            dy = Y_axes[iy + 1] - Y_axes[iy]
            total_G_applied += gamma * beamY_b * beamY_h * dy

for lev in range(nLevels - 1):
    h = heights[lev + 1] - heights[lev]
    for ix in range(nX):
        for iy in range(nY):
            if not (existe(ix, iy, lev) and existe(ix, iy, lev + 1)
                    and hay_pilar(ix, iy)):
                continue
            total_G_applied += ((gamma_acero * A_pm)
                                if columna_metalica(ix, iy)
                                else (gamma * A_col)) * h

# Peso propio de los muros, tramo a tramo (no son iguales en todos los
# pisos). Es un conteo independiente del de apply_gravity: aqui se suma
# por geometria, alla se aplico por nodos.
for (im, lev), _tag in WALL.items():
    h = heights[lev + 1] - heights[lev]
    total_G_applied += gamma * MUROS_PROPS[im][2] * h

print(f"\nTotal Dead Load Applied (G):  {total_G_applied:.2f} kN")
print(f"Total Live Load Applied (Q):  {total_Q_applied:.2f} kN")

sum_Rz_G = sum(results['G']['reactions'][nid][2] for nid in support_nodes)
sum_Rz_Q = sum(results['Q']['reactions'][nid][2] for nid in support_nodes)

print(f"\nDead Load (G):")
print(f"  Applied:   {total_G_applied:>14.2f} kN")
print(f"  Reactions: {sum_Rz_G:>14.2f} kN  (error: {abs(total_G_applied - sum_Rz_G):.6f} kN)")

print(f"\nLive Load (Q):")
print(f"  Applied:   {total_Q_applied:>14.2f} kN")
print(f"  Reactions: {sum_Rz_Q:>14.2f} kN  (error: {abs(total_Q_applied - sum_Rz_Q):.6f} kN)")

# Corte basal real: COEF_SISMICO por el peso sismico. Antes estaba
# fijo en 360 kN, y al cambiar el sismo el chequeo comparaba
# contra un numero que ya no correspondia.
total_lateral = COEF_SISMICO * sum(peso_sismico().values())

# En horizontal solo suman los apoyos que TIENEN restringido ux/uy, o
# sea los de la base. Los arranques de muro sobre la base tienen libres
# ux, uy y rz porque los gobierna el diafragma; lo que nodeReaction
# devuelve ahi en fx/fy es la fuerza del vinculo del diafragma, que es
# INTERNA. Sumarla hacia fallar EX por 10312 kN y EY por 3421 kN.
# En vertical si suman: uz esta restringido y es una reaccion real.
apoyos_horizontales = [n for n in support_nodes
                       if n not in set(apoyos_muro_sobre_base)]
sum_Rx_EX = sum(results['EX']['reactions'][nid][0] for nid in apoyos_horizontales)
sum_Ry_EY = sum(results['EY']['reactions'][nid][1] for nid in apoyos_horizontales)

print(f"\nLateral Load EX:")
print(f"  Applied:   {total_lateral:>14.2f} kN")
print(f"  Reactions: {sum_Rx_EX:>14.2f} kN  (error: {abs(total_lateral + sum_Rx_EX):.6f} kN)")

print(f"\nLateral Load EY:")
print(f"  Applied:   {total_lateral:>14.2f} kN")
print(f"  Reactions: {sum_Ry_EY:>14.2f} kN  (error: {abs(total_lateral + sum_Ry_EY):.6f} kN)")

# =============================================================================
# MAX DISPLACEMENTS
# =============================================================================
print("\n" + "=" * 60)
print("MAXIMUM DISPLACEMENTS SUMMARY")
print("=" * 60)
for lc in ['G', 'Q', 'EX', 'EY']:
    d = results[lc]['displacements']
    max_ux = max(abs(v[0]) for v in d.values())
    max_uy = max(abs(v[1]) for v in d.values())
    max_uz = max(abs(v[2]) for v in d.values())
    print(f"  {lc:3s}: UX_max = {max_ux:.6f} m, UY_max = {max_uy:.6f} m, UZ_max = {max_uz:.6f} m")

# =============================================================================
# SAVE JSON
# =============================================================================
results['model_info'] = {
    'n_nodes': total_nodes,
    'n_elements': nElements,
    'n_columns': nColumns,
    'n_xbeams': nXbeams,
    'n_ybeams': nYbeams,
    'n_levels': nLevels,
    'n_fixed_supports': len(support_nodes),
    'dimensions_m': f"{X_axes[-1] - X_axes[0]:.1f} x {Y_axes[-1] - Y_axes[0]:.1f}",
    'height_m': heights[-1],
    'concrete_fpc_MPa': fpc,
    'concrete_E_MPa': round(Ec, 1),
    'column_section': f"{col_b*100:.0f}x{col_h*100:.0f} cm",
    'beam_x_section': f"{beamX_b*100:.0f}x{beamX_h*100:.0f} cm",
    'beam_y_section': f"{beamY_b*100:.0f}x{beamY_h*100:.0f} cm",
    'slab_thickness_m': slab_t,
}

results['node_coordinates'] = {str(k): v for k, v in node_coords.items()}

results['equilibrium_check'] = {
    'G_applied_kN': round(total_G_applied, 2),
    'G_reaction_kN': round(sum_Rz_G, 2),
    'G_error_kN': round(abs(total_G_applied - sum_Rz_G), 6),
    'Q_applied_kN': round(total_Q_applied, 2),
    'Q_reaction_kN': round(sum_Rz_Q, 2),
    'Q_error_kN': round(abs(total_Q_applied - sum_Rz_Q), 6),
    'EX_applied_kN': round(total_lateral, 2),
    'EX_reaction_kN': round(sum_Rx_EX, 2),
    'EX_error_kN': round(abs(total_lateral + sum_Rx_EX), 6),
    'EY_applied_kN': round(total_lateral, 2),
    'EY_reaction_kN': round(sum_Ry_EY, 2),
    'EY_error_kN': round(abs(total_lateral + sum_Ry_EY), 6),
}

output_path = os.path.join('results', 'benchmark_results.json')
with open(output_path, 'w') as f:
    json.dump(results, f, indent=2)

print(f"\nResults saved to: {output_path}")
print("\nDone!")

# =============================================================================
# EXPORT TO UNITY (automatic visualization)
# =============================================================================
try:
    import export_unity

    export_unity.export_model(
        X_axes, Y_axes, heights,
        col_tags=col_list,
        bx_tags=xbeam_list,
        by_tags=ybeam_list,
        supports=support_nodes,
        label="Edificio de Ingenieria - Universidad de los Andes",
        extra={
            "n_columns": nColumns,
            "n_xbeams": nXbeams,
            "n_ybeams": nYbeams,
            "n_levels": nLevels,
            'dimensions_m': f"{X_axes[-1] - X_axes[0]:.1f} x {Y_axes[-1] - Y_axes[0]:.1f}",
            'height_m': heights[-1],
            "concrete_fpc_MPa": fpc,
        },
        results_file="results/benchmark_results.json",
    )
    print("Unity: model.json actualizado (el visor se recarga solo).")
except ImportError:
    print("(export_unity.py no encontrado; Unity no se actualiza)")
