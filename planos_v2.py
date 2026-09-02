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


# ================================================================
# PLANTAS
# ================================================================
# Una lamina puede traer VARIAS plantas, cada una dibujada en un
# origen distinto. No se pueden comparar coordenadas crudas entre
# plantas ni entre laminas.
#
# Se separan por su TITULO (capa RLA-TEXTOS2), que va SIEMPRE debajo
# de su planta: cada titulo abre una banda en Y que llega hasta el
# titulo siguiente. Verificado en las cuatro laminas.
#
# Despues cada planta se lleva a un sistema comun por su propia
# grilla, usando el cruce eje E x eje 3 como datum. La comprobacion de
# que la traslacion quedo bien es que un mismo muro caiga en
# coordenadas identicas desde laminas distintas.

DATUM_X, DATUM_Y = 'E', '3'      # ejes con que se referencia todo

# Cota de la losa de cada planta, leida del rotulo que acompana al
# titulo. Se rellena al vuelo desde el dibujo.
_RE_COTA = re.compile(r"NIVEL\s+SUPERIOR\s+LOSA\s*([+-]?\d+[.,]\d+)", re.I)
_RE_TITULO = re.compile(r"^PLANTA\s+(FUNDACIONES|CIELO\s+.+)$", re.I)


def plantas(hoja):
    """
    Plantas que trae una lamina, de abajo hacia arriba en el dibujo.

    Devuelve [{'titulo','cota','y_desde','y_hasta','dx','dy'}] donde
    (dx, dy) es lo que hay que SUMAR a las coordenadas de esa planta
    (en metros) para llevarla al sistema comun.

    'cota' es la cota real de la losa en metros, o None si el dibujo
    no la trae (la planta de fundaciones no la declara asi).
    """
    titulos, cotas = [], []
    for e, capa in entidades(hoja):
        if e.dxftype() not in ('TEXT', 'MTEXT'):
            continue
        t = texto_de(e)
        if not t or len(t) > 80:
            continue
        y = e.dxf.insert.y * ESCALA
        if _RE_TITULO.match(t):
            titulos.append((y, t))
        m = _RE_COTA.search(t)
        if m:
            cotas.append((y, float(m.group(1).replace(',', '.'))))

    if not titulos:
        return []
    titulos.sort()

    # Cada titulo abre una banda que llega hasta el titulo siguiente.
    out = []
    for i, (y, t) in enumerate(titulos):
        y_hasta = titulos[i + 1][0] if i + 1 < len(titulos) else float('inf')
        # La cota que acompana a este titulo es la que cae en su banda.
        cerca = [c for cy, c in cotas if y - 2.0 <= cy < y_hasta]
        out.append({
            'titulo': re.sub(r"\s+", " ", t).strip(),
            'cota': cerca[0] if cerca else None,
            'y_desde': y,
            'y_hasta': y_hasta,
        })
    return out


def _en_banda(y, planta):
    return planta['y_desde'] <= y < planta['y_hasta']


# Laminas con geometria de planta, en orden de lectura.
HOJAS_PLANTA = ('2017_67-100', '2017_67-101', '2017_67-102', '2017_67-103')


def todas_las_plantas():
    """
    Las plantas de todas las laminas, ya referenciadas a un sistema
    comun y ordenadas por cota.

    El sistema comun es el de la PLANTA DE FUNDACIONES: su cruce
    eje E x eje 3 queda donde esta, y las demas plantas se trasladan
    para que su propio cruce E x 3 caiga en el mismo punto.

    Cada planta trae 'hoja', 'titulo', 'cota', 'dx', 'dy'.
    """
    base = None
    crudas = []
    for hoja in HOJAS_PLANTA:
        for pl in plantas(hoja):
            ex, e3 = datum_de(hoja, pl)
            if ex is None or e3 is None:
                continue
            pl = dict(pl, hoja=hoja, datum=(ex, e3))
            crudas.append(pl)
            if hoja == HOJAS_PLANTA[0] and base is None:
                base = (ex, e3)

    if base is None:
        raise RuntimeError("No se pudo fijar el datum de la fundacion")

    for pl in crudas:
        pl['dx'] = base[0] - pl['datum'][0]
        pl['dy'] = base[1] - pl['datum'][1]

    # De abajo hacia arriba. La fundacion no declara cota en el titulo,
    # asi que va primera.
    crudas.sort(key=lambda q: (q['cota'] is not None,
                               q['cota'] if q['cota'] is not None else 0.0))
    return crudas


def datum_de(hoja, planta):
    """
    Coordenadas del cruce eje E x eje 3 DENTRO de una planta, en metros.
    Es el punto con que se referencia esa planta.
    """
    v, h = ejes(hoja, planta)
    if DATUM_X not in v or DATUM_Y not in h:
        return None, None
    return v[DATUM_X][0][0], h[DATUM_Y][0][0]


def _componentes(segs, tol=1.0):
    """
    Agrupa segmentos que se tocan (union-find sobre los extremos).

    Un pilar se dibuja como un rectangulo cerrado de 4 lineas: sus
    cuatro segmentos quedan en una misma componente. Sirve igual para
    cualquier contorno cerrado.
    """
    padre = list(range(len(segs)))

    def raiz(i):
        while padre[i] != i:
            padre[i] = padre[padre[i]]
            i = padre[i]
        return i

    def unir(i, j):
        ri, rj = raiz(i), raiz(j)
        if ri != rj:
            padre[ri] = rj

    # Los extremos se indexan en una rejilla para no comparar todos
    # contra todos: con 200 segmentos da igual, pero las plantas
    # grandes tienen miles.
    rejilla = defaultdict(list)
    for i, (x1, y1, x2, y2) in enumerate(segs):
        for px, py in ((x1, y1), (x2, y2)):
            rejilla[(round(px / tol), round(py / tol))].append(i)

    for (gx, gy), idxs in list(rejilla.items()):
        vecinos = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                vecinos += rejilla.get((gx + dx, gy + dy), [])
        for i in idxs:
            for j in vecinos:
                if i != j:
                    unir(i, j)

    grupos = defaultdict(list)
    for i in range(len(segs)):
        grupos[raiz(i)].append(i)
    return list(grupos.values())


def pilares(hoja, planta=None, offset=(0.0, 0.0)):
    """
    Pilares de una lamina, en METROS.

    Devuelve [{'x','y','bx','by','n'}]: centro, lados y cuantos
    segmentos formaban el contorno. Se reconstruyen agrupando las
    lineas de RLE-PILAR que se tocan; un pilar rectangular son 4.

    Con 'planta' se queda solo con los de esa banda, y con 'offset'
    los lleva al sistema comun.

    Se descartan las agrupaciones que no cierran un rectangulo
    razonable, para no inventar pilares donde el dibujo trae otra cosa.
    """
    segs = []
    for e, _c in entidades(hoja, {'RLE-PILAR'}):
        if e.dxftype() == 'LINE':
            a, b = e.dxf.start, e.dxf.end
            if planta is not None and not (
                    _en_banda(a.y * ESCALA, planta)
                    and _en_banda(b.y * ESCALA, planta)):
                continue
            segs.append((a.x, a.y, b.x, b.y))

    out = []
    for grupo in _componentes(segs):
        xs, ys = [], []
        for i in grupo:
            x1, y1, x2, y2 = segs[i]
            xs += [x1, x2]
            ys += [y1, y2]
        bx, by = max(xs) - min(xs), max(ys) - min(ys)

        # Un pilar mide entre 15 cm y 3 m de lado. Fuera de eso es
        # otra cosa (una linea suelta, o varios pilares pegados).
        if not (15.0 <= bx <= 300.0 and 15.0 <= by <= 300.0):
            continue
        out.append({
            'x': (max(xs) + min(xs)) / 2.0 * ESCALA + offset[0],
            'y': (max(ys) + min(ys)) / 2.0 * ESCALA + offset[1],
            'bx': bx * ESCALA,
            'by': by * ESCALA,
            'n': len(grupo),
        })
    return out


def ejes(hoja, planta=None, offset=(0.0, 0.0)):
    """
    Ejes de una lamina, en METROS.

    Devuelve (verticales, horizontales), cada uno
    {etiqueta: [(coordenada, corrimiento_del_globo)]}:

      verticales   -> corren en Y, los define su X
      horizontales -> corren en X, los define su Y

    Con 'planta' se queda solo con los globos de esa banda; con
    'offset' lleva las coordenadas al sistema comun.

    La orientacion NO se adivina: la da la linea de eje a la que se
    llega siguiendo el quiebre.
    """
    lin = _lineas(hoja, 'RLE-EJES')
    verticales, horizontales = {}, {}

    for etiqueta, cx, cy in globos(hoja):
        if planta is not None and not _en_banda(cy * ESCALA, planta):
            continue
        coord, vertical, corrim = eje_real(cx, cy, lin)
        if coord is None:
            continue
        if vertical:
            verticales.setdefault(etiqueta, []).append(
                (coord * ESCALA + offset[0], corrim * ESCALA))
        else:
            horizontales.setdefault(etiqueta, []).append(
                (coord * ESCALA + offset[1], corrim * ESCALA))
    return verticales, horizontales
