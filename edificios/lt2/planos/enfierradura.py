# -*- coding: utf-8 -*-
r"""
================================================================
 enfierradura.py  -  EL FIERRO DE LOS PILARES, DESDE LA ELEVACION
================================================================
 Lee las laminas de elevacion y devuelve, para cada pilar y cada
 piso, el juego de estribos y trabas que el plano le pone.

 ----------------------------------------------------------------
 DONDE ESTA EL FIERRO EN ESTE JUEGO DE PLANOS
 ----------------------------------------------------------------
 No en las plantas: las 200/201/202 son armadura de LOSA y las
 101/102 son encofrado. El fierro de un pilar esta en la ELEVACION
 del eje, escrito justo debajo del rotulo de la seccion:

     P.70x70          <- el rotulo, capa RLE-TEXTOS-1
     E%%C12a10        <- estribo, capa RLA-TEXTOS-FE
     +3T%%C12a10      <- mas 3 trabas
     +3TL%%C12a10     <- mas 3 trabas longitudinales

 Cada pilar aparece en las DOS elevaciones perpendiculares que lo
 cruzan, pero detallado en UNA sola: la otra dice

     VER ELEV. EJE B

 Esa referencia cruzada es lo que evita contar dos veces. Y cierra:
 de los 80 rotulos P.70x70 del juego, 40 traen fierro y 40 remiten.

 ----------------------------------------------------------------
 LA TRAMPA: EL VECINO MAS CERCANO ES LA VIGA
 ----------------------------------------------------------------
 Alrededor del rotulo de un pilar hay llamadas de fierro que NO son
 suyas: las de las vigas que llegan al nudo, con su linea de
 referencia apuntando a la viga. Son las mas cercanas de todas.

     34ED%%C10a10  L:7+7%%C10      <- viga, no pilar

 Buscar "el texto de fierro mas cercano al rotulo" da la respuesta
 equivocada y no avisa. Lo que distingue al fierro del pilar es que
 esta DEBAJO del rotulo y dentro de su ancho: las llamadas de viga
 salen hacia el lado, fuera de la franja. Por eso la busqueda es
 direccional (solo hacia abajo, ver VENTANA_*) y no un radio.

 ----------------------------------------------------------------
 DE LA LAMINA A LA PLANTA
 ----------------------------------------------------------------
 En una elevacion la coordenada horizontal es la coordenada de
 planta del eje PERPENDICULAR, corrida por el origen de la lamina.
 El corrimiento se DERIVA de las burbujas de eje que la propia
 elevacion dibuja, no se supone:

     elevacion EJE B:  burbuja '3' en x=8.03  y el eje 3 esta en
                       11.047  ->  corrimiento 3.017 m

 Se toma la MEDIANA de todas las burbujas reconocidas. Hace falta:
 en la elevacion del eje 1 las burbujas de A', A, B y C dan 93.125
 pero las de D y D' estan dibujadas 45 cm corridas. Con la mediana
 los pilares caen igual en su sitio -- se verifico contra el modelo,
 los tres del eje 1 quedan en 22.355, 32.355 y 42.355 m.

 ----------------------------------------------------------------
 LO QUE ESTE MODULO NO PUEDE DAR
 ----------------------------------------------------------------
 El fierro LONGITUDINAL del pilar. No esta en la elevacion, ni en
 las plantas de encofrado, ni como circulos de barra en seccion
 (los unicos CIRCLE del juego son burbujas de eje), ni en las
 laminas de detalles tipicos. Lo que el plano da para un pilar es
 su juego de estribos y trabas.

 Como el longitudinal es justamente lo que manda en la capacidad a
 momento, hay que declararlo aparte, en el perfil, con su criterio
 escrito. Este modulo devuelve lo que el plano dice y nada mas; que
 el supuesto se vea como supuesto es el punto.
================================================================
"""
from __future__ import annotations

import collections
import re

import ezdxf

try:
    from . import lectura
except ImportError:                            # corriendo suelto
    import lectura                             # noqa: F401

# El nombre del XREF que trae una elevacion: 'EJE 1', "EJE A'",
# "EJE D-D'". Cada uno es un dibujo aparte con su propio origen.
ES_ELEVACION = re.compile(r'^EJE\s+\S', re.I)

# Rotulo de seccion de un pilar: 'P.70x70', 'P. 70 x 70', 'P.30x70'.
ROTULO_PILAR = re.compile(r'^P\.\s*(\d+)\s*[xX]\s*(\d+)\s*$')

# Una llamada de fierro. En AutoCAD el simbolo de diametro se
# escribe '%%C', asi que 'E%%C12a10' es "estribo fi 12 cada 10".
#
#   [+] [n] TIPO %%C diametro a separacion
#
# TIPO segun la simbologia de la lamina 000:
#   E    estribo          ED  2 estribos desplazados
#   ET   3 estribos       T   traba          TL  traba longitudinal
LLAMADA = re.compile(
    r'^\+?\s*(\d*)\s*(ED|ET|E|TL|T)\s*%%C\s*(\d+)\s*a\s*(\d+)\s*$', re.I)

# Fierro longitudinal de punta de muro: 'L:5+5%%C10' son cinco barras
# fi 10 en cada cara del machon.
LONGITUDINAL = re.compile(
    r'^L\s*:\s*(\d+)\s*\+\s*(\d+)\s*%%C\s*(\d+)\s*$', re.I)

# Remision al otro eje: 'VER ELEV. EJE B'
REMISION = re.compile(r'VER\s+ELEV\.?\s+EJE\s+(.+?)\s*$', re.I)

# Ventana de busqueda del fierro de un pilar, respecto de su rotulo,
# en metros. Hacia ABAJO porque el plano escribe el estribo debajo
# del rotulo, y estrecha porque las llamadas de viga salen de la
# franja del pilar.
VENTANA_ABAJO = (0.05, 0.80)    # cuanto mas abajo que el rotulo
VENTANA_LADO = 1.20             # cuanto a los lados del rotulo

# La remision ('VER ELEV. EJE B') se escribe mas abajo que el estribo
# -- 1.15 m en el eje 2 -- asi que necesita su propia ventana. Sigue
# siendo segura: entre piso y piso hay 3.96 m.
VENTANA_REMISION = 1.60

# Las tres lineas del juego de un pilar van pegadas: 0.16 a 0.19 m
# entre si. Un salto mayor significa que la siguiente llamada ya es de
# otra cosa -- el estribo de un muro vecino, por ejemplo -- aunque
# todavia caiga dentro de la ventana.
SALTO_MAXIMO = 0.35

# Cuanto puede alejarse una burbuja de eje del corrimiento mediano
# para seguir contando en el ajuste, en metros.
TOL_BURBUJA = 0.30


def bloques_con_atributos(ruta, perfil, prof_max=3):
    r"""
    Los INSERT con atributos de cada elevacion de la lamina, en el
    MISMO marco y las MISMAS unidades que hojas_de_elevacion(): metros,
    coordenadas de lamina. Devuelve {nombre_xref: [bloque, ...]}.

    ----------------------------------------------------------------
    POR QUE NO SIRVE LA HOJA APLANADA
    ----------------------------------------------------------------
    lectura.leer() convierte cada ATTRIB en un Texto suelto, y ahi se
    pierde de que CAMPO era. El bloque de malla de un muro tiene seis
    campos y aplanado quedan seis textos: '30', '12a10', '12a20'...
    Sin el nombre del campo no hay forma de saber cual es el espesor,
    cual la malla horizontal y cual la vertical.

    El fierro de un pilar si se puede leer aplanado, porque su texto
    se explica solo ('E%%C12a10'). El de un muro no.

    Las coordenadas salen del MISMO recorrido que la hoja -- por el
    INSERT del modelspace, no por el bloque -- porque el corrimiento a
    coordenadas de planta se calcula con las burbujas de eje de la
    hoja. Mezclar los dos marcos pone los muros a decenas de metros.
    """
    doc = ezdxf.readfile(ruta)
    f = perfil.factor
    salida = {}

    def recorrer(entidades, prof, acumulador):
        for e in entidades:
            if e.dxftype() != 'INSERT':
                continue
            attrs = {a.dxf.tag.upper(): (a.dxf.text or '').strip()
                     for a in getattr(e, 'attribs', [])}
            if attrs:
                acumulador.append({
                    'x': float(e.dxf.insert[0]) * f,
                    'y': float(e.dxf.insert[1]) * f,
                    'bloque': e.dxf.name,
                    'attrs': attrs,
                })
            if prof < prof_max:
                try:
                    recorrer(list(e.virtual_entities()), prof + 1, acumulador)
                except Exception:
                    pass

    for e in doc.modelspace():
        if e.dxftype() != 'INSERT' or not ES_ELEVACION.match(e.dxf.name):
            continue
        try:
            hijas = list(e.virtual_entities())
        except Exception:
            continue
        acc = []
        for att in getattr(e, 'attribs', []):
            pass
        recorrer(hijas, 1, acc)
        salida[e.dxf.name] = acc
    return salida


# Una malla: '12a20' es fi 12 cada 20 cm.
MALLA = re.compile(r'^(\d+)\s*a\s*(\d+)$', re.I)


def parsear_malla(texto):
    """'12a20' -> {'diametro_mm': 12, 'separacion_cm': 20}"""
    m = MALLA.match((texto or '').strip())
    if not m:
        return None
    return {'diametro_mm': int(m.group(1)),
            'separacion_cm': int(m.group(2)),
            'texto': texto.strip()}


def parsear_longitudinal(texto):
    """'L:5+5%%C10' -> 5 barras fi 10 por cara, 10 en total."""
    m = LONGITUDINAL.match((texto or '').strip())
    if not m:
        return None
    a, b, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return {'por_cara': [a, b], 'cantidad': a + b, 'diametro_mm': d,
            'texto': texto.strip()}


def machones(hoja, perfil, dx, a_cota, niveles):
    r"""
    Los muros que el plano detalla COMO UNA COLUMNA ANCHA en vez de
    con malla repartida.

    ----------------------------------------------------------------
    HAY DOS FORMAS DE ARMAR UN MURO Y EL PLANO USA LAS DOS
    ----------------------------------------------------------------
    Un muro largo y delgado lleva MALLA: dos cortinas repartidas a lo
    largo, mas barras en las puntas. Eso viene en un bloque con
    atributos (ver mallas_de_muro).

    Un muro corto y grueso -- el M 0.60x2.92 del poniente, 60 cm de
    espesor por 2.92 de largo -- se arma como un machon: estribos y
    trabas como una columna, y el longitudinal escrito aparte:

        E%%C12a10  +3T%%C12a10  +3TL%%C12a10     el juego transversal
        L:5+5%%C10                               cinco barras por cara

    En la elevacion del eje A' no hay NINGUN bloque de malla -- se
    comprobo: cero atributos ESPESOR en sus 150 bloques -- y por eso
    esos diez elementos quedaban sin fierro aunque el plano si lo da.

    Lo bueno es que el 'L:' dice cuantas barras hay. En una columna
    ese numero habia que deducirlo del numero de trabas; aca esta
    escrito.
    """
    salida = []
    for t in hoja.textos_de(perfil, 'enfierradura'):
        s = ' '.join(t.texto.split())
        llamada = parsear_llamada(s)
        largo = parsear_longitudinal(s)
        if not (llamada or largo):
            continue
        cota = a_cota(t.y) if a_cota else None
        piso, cota_piso = piso_de_cota(cota, niveles)
        salida.append({
            'x_planta': round(t.x + dx, 4),
            'cota_leida': round(cota, 3) if cota is not None else None,
            'piso': piso, 'cota': cota_piso,
            'llamada': llamada, 'longitudinal': largo,
            'texto': s,
        })
    return salida


def mallas_de_muro(bloques):
    r"""
    Los bloques de malla de una elevacion, ya interpretados.

    El bloque se dibuja sobre el muro y se lee asi:

        M.H.A. e=<ESPESOR>      Muro Hormigon Armado, espesor en cm
        D.M. %%C<MALLA_1>       Doble Malla: las dos direcciones
        H.   %%C<MALLA_2>       solo la horizontal
        V.   %%C<MALLA_3>       solo la vertical

    Cuando vienen H y V por separado, mandan sobre la D.M. La que
    importa para la capacidad a flexion en el plano es la VERTICAL:
    es la que se tracciona cuando el muro flecta.

    'doble' no es un detalle: son DOS cortinas, una por cara, asi que
    el area por metro es el doble de la de una malla suelta. Contarla
    simple deja el muro con la mitad del acero que tiene.
    """
    salida = []
    for b in bloques:
        a = b['attrs']
        if not any(k in a for k in ('MALLA_1', 'MALLA_2', 'MALLA_3')):
            continue
        try:
            espesor = float(a.get('ESPESOR', '') or 0) / 100.0
        except ValueError:
            espesor = 0.0
        dm = parsear_malla(a.get('MALLA_1'))
        h = parsear_malla(a.get('MALLA_2'))
        v = parsear_malla(a.get('MALLA_3'))
        if not (dm or h or v):
            continue
        salida.append({
            'x': b['x'], 'y': b['y'],
            'espesor_m': espesor,
            'doble_malla': dm,
            'horizontal': h or dm,
            'vertical': v or dm,
            'capas': 2,          # D.M. = doble malla, una por cara
            'texto': 'e=%s D.M.=%s H=%s V=%s'
                     % (a.get('ESPESOR', '-'), a.get('MALLA_1', '-'),
                        a.get('MALLA_2', '-'), a.get('MALLA_3', '-')),
        })
    return salida


def eje_de(nombre_bloque):
    r"""
    Que eje dibuja este XREF.

        'EJE B'      -> 'B'
        "EJE A'"     -> "A'"     el eje auxiliar es OTRO eje
        "EJE D-D'"   -> 'D'      una sola elevacion para los dos

    El apostrofo se conserva salvo cuando viene en un par 'D-D'': ahi
    la elevacion es una y se le atribuye al eje principal.
    """
    n = re.sub(r'^EJE\s+', '', nombre_bloque.strip(), flags=re.I)
    return n.split('-')[0].strip()


def hojas_de_elevacion(ruta, perfil):
    """
    Las elevaciones de UNA lamina, cada una por separado.

    ----------------------------------------------------------------
    POR QUE NO SIRVE LEER LA LAMINA ENTERA
    ----------------------------------------------------------------
    Una lamina puede traer dos elevaciones: la 305 es 'ELEVACION EJES
    C, D-D''. Cada una es un XREF distinto, dibujado en su propio
    origen y pegado en la lamina en un sitio distinto.

    Leyendo la lamina de corrido, las burbujas de eje de las dos
    elevaciones se mezclan y el corrimiento que sale de su mediana no
    es el de ninguna de las dos: los pilares terminan a decenas de
    metros de donde estan. Y no falla, da coordenadas.

    Por eso cada XREF se lee en su propia Hoja.
    """
    doc = ezdxf.readfile(ruta)
    hojas = {}
    for e in doc.modelspace():
        if e.dxftype() != 'INSERT' or not ES_ELEVACION.match(e.dxf.name):
            continue
        try:
            hijas = list(e.virtual_entities())
        except Exception:
            continue
        h = lectura.Hoja(ruta, perfil.factor)
        lectura._recorrer(hijas, h, perfil.factor, 1)
        for att in getattr(e, 'attribs', []):
            lectura._agregar(h, att, perfil.factor)
        hojas[e.dxf.name] = h
    return hojas


def parsear_llamada(texto):
    """
    'E%%C12a10' -> {'tipo': 'E', 'cantidad': 1, 'diametro_mm': 12,
                    'separacion_cm': 10}
    Devuelve None si el texto no es una llamada de fierro.
    """
    m = LLAMADA.match(texto.strip())
    if not m:
        return None
    n, tipo, diam, sep = m.groups()
    return {
        'tipo': tipo.upper(),
        'cantidad': int(n) if n else 1,
        'diametro_mm': int(diam),
        'separacion_cm': int(sep),
        'texto': texto.strip(),
    }


def _corrimiento(hoja, perfil, grid):
    """
    Cuanto hay que sumarle a la x de esta elevacion para caer en la
    coordenada de planta. Sale de las burbujas de eje que la lamina
    dibuja; se devuelve tambien con que burbujas se calculo.
    """
    candidatos = []
    for t in hoja.textos_de(perfil, 'ejes_rotulos'):
        nombre = t.texto.strip()
        if nombre in grid:
            candidatos.append((grid[nombre] - t.x, nombre, t.x))
    if not candidatos:
        return None, []

    valores = sorted(c[0] for c in candidatos)
    mediana = valores[len(valores) // 2]
    usadas = [c for c in candidatos if abs(c[0] - mediana) <= TOL_BURBUJA]
    if not usadas:
        return mediana, []
    # Con las que sobrevivieron se recalcula, para no quedarse con el
    # valor de una sola burbuja cuando hay varias buenas.
    finos = sorted(c[0] for c in usadas)
    return finos[len(finos) // 2], [(c[1], round(c[0], 4)) for c in candidatos]


def _filas(valores, tol=0.30):
    """Agrupa coordenadas en filas; devuelve los centros ordenados."""
    filas = []
    for v in sorted(valores):
        if filas and v - filas[-1][-1] <= tol:
            filas[-1].append(v)
        else:
            filas.append([v])
    return [sum(f) / len(f) for f in filas]


def extraer(hoja, perfil, grid, niveles=None):
    """
    Lee una lamina de elevacion. Devuelve (pilares, auditoria).

    Cada pilar es un dict con su posicion en planta, el piso, la
    seccion rotulada y sus llamadas de fierro -- o, si la lamina
    remite a otra, a que eje remite.

    'niveles' es la lista de cotas del edificio, de menor a mayor.
    Si viene, cada pilar sale con la cota de su piso; si no, sale
    solo con el indice de la fila.
    """
    aud = {'archivo': hoja.archivo}

    dx, burbujas = _corrimiento(hoja, perfil, grid)
    aud['burbujas'] = burbujas
    aud['corrimiento_m'] = None if dx is None else round(dx, 4)
    if dx is None:
        aud['problema'] = ('no se reconocio ninguna burbuja de eje: sin eso '
                           'no se puede llevar la elevacion a coordenadas '
                           'de planta')
        return [], aud

    rotulos = []
    for t in hoja.textos:
        m = ROTULO_PILAR.match(t.texto.strip())
        if m:
            rotulos.append((t, int(m.group(1)), int(m.group(2))))
    aud['rotulos'] = len(rotulos)
    if not rotulos:
        return [], aud

    # Los rotulos se ordenan en filas horizontales, una por piso.
    filas = _filas([t.y for t, _b, _h in rotulos])
    aud['filas'] = len(filas)

    fierro = [t for t in hoja.textos_de(perfil, 'enfierradura')]
    aud['textos_de_fierro'] = len(fierro)

    pilares = []
    for t, b_cm, h_cm in rotulos:
        # De todas las llamadas de fierro, las que caen DEBAJO de este
        # rotulo y dentro de su franja. Ver la nota del encabezado
        # sobre por que no sirve el vecino mas cercano.
        cerca = []
        for f in fierro:
            dy = t.y - f.y
            if not (VENTANA_ABAJO[0] <= dy <= VENTANA_REMISION):
                continue
            if abs(f.x - t.x) > VENTANA_LADO:
                continue
            # Si hay otro rotulo mas cerca en horizontal, la llamada es
            # de ese otro pilar.
            otro = min(rotulos, key=lambda r: abs(r[0].x - f.x))
            if abs(otro[0].x - f.x) < abs(t.x - f.x) - 1e-9:
                continue
            cerca.append(f)
        cerca.sort(key=lambda f: -f.y)

        # La remision puede estar mas abajo que el juego de estribos.
        remite = None
        for f in cerca:
            m = REMISION.search(f.texto)
            if m:
                remite = m.group(1).strip()
                break

        # El juego del pilar es la CADENA de llamadas que arranca justo
        # debajo del rotulo. Se corta en el primer salto grande: lo que
        # viene despues ya es de otro elemento.
        llamadas, sueltos = [], []
        anterior = t.y
        for f in cerca:
            if t.y - f.y > VENTANA_ABAJO[1]:
                break
            if anterior - f.y > SALTO_MAXIMO:
                break
            c = parsear_llamada(f.texto)
            if c:
                llamadas.append(c)
                anterior = f.y
            elif REMISION.search(f.texto):
                continue
            else:
                sueltos.append(f.texto.strip())

        fila = min(range(len(filas)), key=lambda i: abs(filas[i] - t.y))
        pilares.append({
            'x_planta': round(t.x + dx, 4),
            'piso': fila,
            'cota': (round(niveles[fila], 4)
                     if niveles and fila < len(niveles) else None),
            'seccion_cm': [b_cm, h_cm],
            'rotulo': t.texto.strip(),
            'llamadas': llamadas,
            'remite_a': remite,
            'no_reconocido': sueltos,
        })

    con = sum(1 for p in pilares if p['llamadas'])
    aud['con_fierro'] = con
    aud['remiten'] = sum(1 for p in pilares if p['remite_a'] and not p['llamadas'])
    aud['sin_nada'] = sum(1 for p in pilares
                          if not p['llamadas'] and not p['remite_a'])
    return pilares, aud


def mapa_de_cotas(bloques):
    r"""
    Convierte altura de dibujo en COTA REAL, a partir de las marcas de
    nivel que la propia elevacion trae como atributo.

    Devuelve una funcion y -> cota, o None si no hay marcas.

    ----------------------------------------------------------------
    POR QUE NO BASTA AGRUPAR EN FILAS
    ----------------------------------------------------------------
    Repartir los rotulos en filas y numerarlas de abajo hacia arriba
    funciona mientras la elevacion dibuje UN solo elemento por piso.
    En la elevacion de los ejes D-D' hay dos muros, cada uno con sus
    cinco bloques de malla puestos a mano a alturas ligeramente
    distintas: las filas salen diez en vez de cinco y el piso queda
    fuera de rango. No falla, deja la cota en None.

    Las marcas de nivel dan la correspondencia exacta. Se ajusta una
    recta por minimos cuadrados sobre todas ellas, en vez de tomar dos:
    asi una marca mal puesta -- el sello de fundacion, un antepecho --
    no corre todo el resto.
    """
    puntos = []
    for b in bloques:
        for tag, valor in b['attrs'].items():
            if 'nivel' not in b['bloque'].lower() and '%%P' not in tag:
                continue
            t = (valor or '').replace('+', '').strip()
            try:
                cota = float(t)
            except ValueError:
                continue
            puntos.append((b['y'], cota))
    if len(puntos) < 2:
        return None

    n = len(puntos)
    sy = sum(p[0] for p in puntos)
    sc = sum(p[1] for p in puntos)
    syy = sum(p[0] * p[0] for p in puntos)
    syc = sum(p[0] * p[1] for p in puntos)
    den = n * syy - sy * sy
    if abs(den) < 1e-12:
        return None
    a = (n * syc - sy * sc) / den
    b0 = (sc - a * sy) / n
    return lambda y: a * y + b0


def piso_de_cota(cota, niveles, tol=2.5):
    """
    En que piso cae una cota. El piso k va del nivel k al k+1, asi que
    una anotacion a media altura pertenece al piso de ABAJO.
    """
    if cota is None or not niveles:
        return None, None
    for i in range(len(niveles)):
        techo = niveles[i + 1] if i + 1 < len(niveles) else niveles[i] + 3.96
        if niveles[i] - tol <= cota < techo:
            return i, niveles[i]
    return None, None


def barras_sueltas(bloques):
    r"""
    Las barras rotuladas una por una que hay en la elevacion: las de
    borde de muro y las de refuerzo. Cada una trae cuantas son, su
    diametro y su largo.

    Son las que en el dibujo se ven como '3 %%C28 L=950 (50+900)'. A
    diferencia de la malla, que es continua, estas van en un sitio
    concreto -- las puntas del muro -- y son las que mandan en su
    capacidad a flexion.

    El punto de insercion del bloque ES la posicion de la barra: se
    comprobo expandiendo su geometria, que arranca justo ahi.
    """
    salida = []
    for b in bloques:
        a = b['attrs']
        diam = a.get('DIAM') or a.get('DIAMETRO')
        if not diam:
            continue
        try:
            d = int(float(diam))
        except ValueError:
            continue
        cant = a.get('CANT') or a.get('NUM') or '1'
        try:
            n = int(float(cant))
        except ValueError:
            n = 1
        salida.append({
            'x': b['x'], 'y': b['y'],
            'cantidad': n, 'diametro_mm': d,
            'largo': a.get('LARGO') or a.get('TEXTO_FE1') or '',
            'tipo': a.get('TIPO', ''),
        })
    return salida


def extraer_mallas(hoja, bloques, perfil, grid, niveles=None):
    r"""
    Las mallas de muro de una elevacion, ya en coordenadas de planta.
    Devuelve (mallas, auditoria).

    Usa el MISMO corrimiento que los pilares -- el de las burbujas de
    eje de esta hoja -- y la misma reparticion en filas por piso.
    """
    aud = {'archivo': hoja.archivo}
    dx, burbujas = _corrimiento(hoja, perfil, grid)
    aud['corrimiento_m'] = None if dx is None else round(dx, 4)
    if dx is None:
        return [], aud, [], []

    mallas = mallas_de_muro(bloques)
    aud['mallas'] = len(mallas)

    a_cota = mapa_de_cotas(bloques)
    aud['cotas_por_marcas_de_nivel'] = a_cota is not None
    filas = _filas([m['y'] for m in mallas])
    aud['filas'] = len(filas)

    sin_piso = 0
    for m in mallas:
        m['x_planta'] = round(m['x'] + dx, 4)
        if a_cota is not None:
            m['cota_leida'] = round(a_cota(m['y']), 3)
            piso, cota = piso_de_cota(m['cota_leida'], niveles)
        else:
            # Sin marcas de nivel se cae al reparto por filas, que
            # solo vale si la elevacion dibuja un elemento por piso.
            piso = min(range(len(filas)),
                       key=lambda i: abs(filas[i] - m['y']))
            cota = (niveles[piso] if niveles and piso < len(niveles)
                    else None)
        m['piso'] = piso
        m['cota'] = cota
        if piso is None:
            sin_piso += 1
    aud['sin_piso'] = sin_piso

    # Las barras sueltas viajan con la misma transformacion.
    barras = barras_sueltas(bloques)
    for b in barras:
        b['x_planta'] = round(b['x'] + dx, 4)
        if a_cota is not None:
            b['cota_leida'] = round(a_cota(b['y']), 3)
            b['piso'], b['cota'] = piso_de_cota(b['cota_leida'], niveles)
        else:
            b['piso'], b['cota'] = None, None
    aud['barras_sueltas'] = len(barras)

    # Los muros armados como machon, que no traen bloque de malla.
    macho = machones(hoja, perfil, dx, a_cota, niveles)
    aud['llamadas_de_machon'] = len(macho)
    return mallas, aud, barras, macho


def esquemas(pilares):
    """Cuantos pilares comparten cada juego de llamadas."""
    c = collections.Counter()
    for p in pilares:
        if not p['llamadas']:
            continue
        c[' '.join(l['texto'] for l in p['llamadas'])] += 1
    return c


def a_json(pilares):
    """Solo los que traen fierro, listos para el JSON de geometria."""
    return [p for p in pilares if p['llamadas']]
