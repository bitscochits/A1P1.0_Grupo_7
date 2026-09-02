#!/usr/bin/env python3
"""
================================================================
 planos_v2.py -- lectura de los planos estructurales, desde cero
================================================================
 Lee los DXF de C:\\planos_v2 (extraidos del .rar del equipo y
 convertidos con accoreconsole) y devuelve geometria en METROS.

 No asume NADA del modelo anterior: los ejes, las cotas y los
 elementos salen del dibujo cada vez.

 UNIDADES. Los DXF vienen con INSUNITS = 0, o sea sin unidades
 declaradas. Se dedujeron midiendo: el globo de eje mide 87.5 de
 diametro y en el edificio real son 87.5 cm, asi que el dibujo esta
 en CENTIMETROS. ESCALA lo convierte a metros.

 BLOQUES. Casi toda la geometria vive dentro de INSERT. Sin
 explotarlos con virtual_entities() el dibujo se ve practicamente
 vacio.
================================================================
"""

import logging
import math
import os
import re
from collections import defaultdict

# ezdxf avisa por cada ACDB_BLOCKREPRESENTATION_DATA que no sabe
# copiar. Son miles y no afectan la geometria.
logging.getLogger('ezdxf').setLevel(logging.ERROR)
import ezdxf

DIR = r"C:\planos_v2"
ESCALA = 0.01          # el dibujo esta en cm; el modelo en m

# Radio del globo de eje, en unidades de dibujo (cm). Medido: los
# CIRCLE de RLE-EJE tienen 87.5 de diametro.
R_GLOBO = 43.75


# ================================================================
# LECTURA BASE
# ================================================================
_cache = {}


def documento(hoja):
    """Abre una lamina (cacheada: leerlas cuesta segundos)."""
    if hoja not in _cache:
        ruta = os.path.join(DIR, hoja + '.dxf')
        if not os.path.exists(ruta):
            raise FileNotFoundError(ruta)
        _cache[hoja] = ezdxf.readfile(ruta)
    return _cache[hoja]


def aplanar(msp):
    """
    Recorre el dibujo explotando los INSERT, y devuelve (entidad, capa).
    La capa se toma de la subentidad, que es la que vale.
    """
    for e in msp:
        if e.dxftype() == 'INSERT':
            try:
                for sub in e.virtual_entities():
                    yield sub, sub.dxf.layer
            except Exception:
                pass
        else:
            yield e, e.dxf.layer


def texto_de(e):
    """Texto plano de TEXT/MTEXT, sin codigos de formato ni espacios."""
    try:
        t = e.plain_text() if e.dxftype() == 'MTEXT' else e.dxf.text
    except Exception:
        return ""
    return re.sub(r"\s+", " ", t).strip()


def entidades(hoja, capas=None):
    """Lista de (entidad, capa) de una lamina, filtrando por capa."""
    msp = documento(hoja).modelspace()
    out = []
    for e, capa in aplanar(msp):
        if capas is None or capa in capas:
            out.append((e, capa))
    return out


# ================================================================
# EJES
# ================================================================
# Un eje se identifica por su GLOBO: un CIRCLE en RLE-EJE con una
# etiqueta MTEXT adentro. Pero el globo NO siempre esta sobre la linea
# de su eje: cuando dos ejes quedan mas cerca que un diametro, el
# dibujante corre el globo y lo une a su eje con un QUIEBRE (un tramo
# corto perpendicular y luego uno paralelo hasta la linea larga).
#
# Por eso la coordenada del eje NO se lee del globo: se sigue la
# cadena de lineas de RLE-EJES desde el globo hasta la linea LARGA, y
# esa es la que manda.

def _lineas(hoja, capa):
    out = []
    for e, c in entidades(hoja, {capa}):
        if e.dxftype() == 'LINE':
            a, b = e.dxf.start, e.dxf.end
            out.append((a.x, a.y, b.x, b.y))
    return out


def globos(hoja):
    """
    Devuelve [(etiqueta, cx, cy)] de los globos de eje de la lamina.
    La etiqueta es el MTEXT cuyo punto de insercion cae dentro del
    circulo.
    """
    circ, textos = [], []
    for e, capa in entidades(hoja, {'RLE-EJE'}):
        if e.dxftype() == 'CIRCLE':
            circ.append((e.dxf.center.x, e.dxf.center.y, e.dxf.radius))
        elif e.dxftype() in ('TEXT', 'MTEXT'):
            t = texto_de(e)
            if t:
                p = e.dxf.insert
                textos.append((t, p.x, p.y))

    out = []
    for cx, cy, r in circ:
        tol = max(r, R_GLOBO) * 1.4
        dentro = [(t, math.hypot(tx - cx, ty - cy))
                  for t, tx, ty in textos
                  if abs(tx - cx) <= tol and abs(ty - cy) <= tol]
        if dentro:
            dentro.sort(key=lambda z: z[1])
            out.append((dentro[0][0], cx, cy))
    return out


# Una linea de eje recorre la planta: son metros. Un tramo de quiebre
# mide decenas de centimetros. El umbral esta bien lejos de ambos: el
# eje mas corto medido es 2a con 12.8 m, y el quiebre mas largo 45 cm.
LARGO_EJE = 300.0        # cm


def _sale_del_globo(cx, cy, lineas):
    """
    Indice de la linea que SALE del globo, o None.

    Es aquella con un extremo a la distancia del radio del globo: el
    dibujante engancha la linea al borde del circulito, no al centro.
    """
    mejor, mejor_d, mejor_pt = None, None, None
    for i, (x1, y1, x2, y2) in enumerate(lineas):
        for px, py in ((x1, y1), (x2, y2)):
            d = math.hypot(px - cx, py - cy)
            # Ventana amplia alrededor del radio: hay globos con radio
            # algo distinto y lineas que arrancan pegadas al centro.
            if d <= R_GLOBO * 2.5 and (mejor_d is None or d < mejor_d):
                mejor, mejor_d, mejor_pt = i, d, (px, py)
    return mejor, mejor_pt


def eje_real(cx, cy, lineas):
    """
    Coordenada real del eje cuyo globo esta en (cx, cy).

    Sigue la CADENA de lineas desde el globo hasta dar con una linea
    larga, que es la linea de eje propiamente tal. Los tramos cortos
    intermedios son el quiebre con que el dibujante corre un globo
    cuando dos ejes quedan demasiado juntos.

    NO se busca "la linea larga mas cercana": eso pega el eje a su
    vecino cuando su propia linea es corta (le pasa a 2a, que mide
    12.8 m y solo cubre parte de la planta).

    Devuelve (coordenada_cm, es_vertical, corrimiento_cm) o
    (None, None, None).
    """
    i, pt = _sale_del_globo(cx, cy, lineas)
    if i is None:
        return None, None, None

    visitadas = set()
    actual, punto = i, pt

    for _ in range(8):          # tope: un quiebre son 2 o 3 tramos
        if actual in visitadas:
            break
        visitadas.add(actual)
        x1, y1, x2, y2 = lineas[actual]
        dx, dy = abs(x2 - x1), abs(y2 - y1)
        largo = math.hypot(dx, dy)
        vertical = dy > dx

        if largo >= LARGO_EJE:
            coord = (x1 + x2) / 2.0 if vertical else (y1 + y2) / 2.0
            ref = cx if vertical else cy
            return coord, vertical, abs(coord - ref)

        # Tramo corto: es parte del quiebre. Se salta al otro extremo
        # y se busca con que linea sigue.
        ax, ay = (x1, y1)
        bx, by = (x2, y2)
        if math.hypot(punto[0] - ax, punto[1] - ay) < \
           math.hypot(punto[0] - bx, punto[1] - by):
            otro = (bx, by)
        else:
            otro = (ax, ay)

        sig, sig_pt = None, None
        mejor_d = None
        for j, (u1, v1, u2, v2) in enumerate(lineas):
            if j in visitadas:
                continue
            for px, py in ((u1, v1), (u2, v2)):
                d = math.hypot(px - otro[0], py - otro[1])
                if d <= 5.0 and (mejor_d is None or d < mejor_d):
                    sig, sig_pt, mejor_d = j, (px, py), d
        if sig is None:
            break
        actual, punto = sig, sig_pt

    return None, None, None


def ejes(hoja):
    """
    Ejes de una lamina, en METROS.

    Devuelve (verticales, horizontales), cada uno
    {etiqueta: [(coordenada, corrimiento_del_globo)]}:

      verticales   -> corren en Y, los define su X
      horizontales -> corren en X, los define su Y

    La orientacion NO se adivina: la da la linea de eje a la que se
    llega siguiendo el quiebre.
    """
    lin = _lineas(hoja, 'RLE-EJES')
    verticales, horizontales = {}, {}

    for etiqueta, cx, cy in globos(hoja):
        coord, vertical, corrim = eje_real(cx, cy, lin)
        if coord is None:
            continue
        destino = verticales if vertical else horizontales
        destino.setdefault(etiqueta, []).append(
            (coord * ESCALA, corrim * ESCALA))
    return verticales, horizontales
