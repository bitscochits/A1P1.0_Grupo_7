"""
================================================================
 modelo_benchmark.py  -  FUENTE DE VERDAD DEL MODELO
================================================================
 Geometria, material, secciones y cargas del marco de benchmark
 (4 columnas + 4 vigas L, un piso, 4x4x3 m).

 Antes esto estaba DUPLICADO en benchmark_distribuida.py y en
 generar_json_unity.py, con la carga escrita a mano como -11.19.
 Si cambiabas el espesor de losa en un archivo, el otro seguia
 usando el valor viejo en silencio.

 Ahora ambos importan de aqui. Un solo lugar que cambiar.

 Unidades: m, kN, kPa (consistentes).
================================================================
"""

import math
import openseespy.opensees as ops

# ============================================================
# 1. GEOMETRIA
# ============================================================
X = [0.0, 4.0]
Y = [0.0, 4.0]
Z = [0.0, 3.0]

nX, nY, nNivel = len(X), len(Y), len(Z)
nNodosPorPiso = nX * nY

Lx = X[1] - X[0]
Ly = Y[1] - Y[0]


# ============================================================
# 2. MATERIAL  (hormigon G-25)
# ============================================================
fpc = 25.0                                  # MPa
poisson = 0.2
Ec = 4700.0 * math.sqrt(fpc) * 1000.0       # kPa
Gc = Ec / (2.0 * (1.0 + poisson))
gamma = 25.0                                # kN/m3


# ============================================================
# 3. TORSION
# ============================================================
def J_rectangular(b, h):
    """
    Constante de torsion de Saint-Venant para seccion rectangular
    llena (Timoshenko / Roark):

        J = a * t^3 * [ 1/3 - 0.21*(t/a)*(1 - t^4/(12*a^4)) ]

    con a = lado LARGO, t = lado CORTO.

    Para cuadrada da J = 0.1406*b^4, que para 30x30 son 1.141e-3 m4.

    NOTA: antes el codigo usaba `min(Iy,Iz)*0.3`, que no corresponde a
    ninguna formula y daba 2.025e-4 m4 -> 5.6 veces MENOS rigidez
    torsional de la real. En el benchmark no se nota (marco simetrico,
    torsion ~0), pero en el edificio real con planta irregular y sismo
    EX/EY la torsion si carga las columnas.
    """
    a = max(b, h)   # lado largo
    t = min(b, h)   # lado corto
    return a * t**3 * (1.0/3.0 - 0.21 * (t/a) * (1.0 - t**4 / (12.0 * a**4)))


# ============================================================
# 4. SECCIONES
# ============================================================
# --- Columna cuadrada 30x30 ---
col_b, col_h = 0.30, 0.30
A_col = col_b * col_h
Iy_col = col_b * col_h**3 / 12.0
Iz_col = col_h * col_b**3 / 12.0
J_col = J_rectangular(col_b, col_h)

# --- Viga L (losa colaborante, ala = luz/4 segun ACI) ---
# Calculada geometricamente en la Semana 1; ver CLAUDE.md.
A_vig = 0.237500
Iy_vig = 2.07271107e-02   # lateral
Iz_vig = 4.62842654e-03   # gravedad
J_vig = 2.03909066e-03


# ============================================================
# 5. CARGAS
# ============================================================
t_losa_carga = 0.15                       # m (espesor de losa para carga)
sobrecarga_terminaciones = 1.5            # kN/m2

q_losa = gamma * t_losa_carga + sobrecarga_terminaciones   # 5.25 kN/m2
q_viva = 2.0                                               # kN/m2


def area_tributaria_viga(luz_viga, luz_transversal):
    r"""
    Area tributaria (m2) de UNA viga de un pano rectangular de losa,
    por reparto a 45 grados desde las esquinas.

        luz_viga        = largo de ESTA viga
        luz_transversal = la otra dimension del pano

    Al trazar las bisectrices a 45 desde las 4 esquinas, el pano queda
    dividido en 4 zonas:

        pano Lx (horizontal) x Ly (vertical), con Ly < Lx:

          +--------------------+
          | \                / |     vigas de luz Lx (LARGAS)  -> TRAPECIO
          |  \______________/  |     vigas de luz Ly (CORTAS)  -> TRIANGULO
          |  /              \  |
          | /                \ |
          +--------------------+

    Formulas (a = luz de esta viga, b = luz transversal):

        b <= a  -> esta viga es la larga  -> trapecio
                   A = b*(2a - b)/4
        b >  a  -> esta viga es la corta  -> triangulo
                   A = a^2/4

    Caso cuadrado (a == b == L): ambas dan L^2/4, o sea A_pano/4.
    Por eso el benchmark no cambia.

    Conservacion: 2*A_larga + 2*A_corta = Lx*Ly siempre (verificado en
    test_areas_tributarias.py para varias relaciones de aspecto).
    """
    a = float(luz_viga)
    b = float(luz_transversal)
    if a <= 0.0 or b <= 0.0:
        raise ValueError(f"Luces deben ser positivas: a={a}, b={b}")

    if b <= a:
        return b * (2.0 * a - b) / 4.0    # trapecio
    return a * a / 4.0                    # triangulo


def poligonos_tributarios(x0, x1, y0, y1):
    r"""
    Vertices de los 4 poligonos tributarios de un pano rectangular,
    trazando bisectrices a 45 grados desde las esquinas.

    Devuelve una lista de 4 dicts:
        {'lado': 'y0'|'y1'|'x0'|'x1',   que viga lo recibe
         'forma': 'trapecio'|'triangulo',
         'vertices': [(x,y), ...],
         'area': m2}

    'y0' es la viga que corre en X sobre y = y0, y asi.

    Geometria: las 4 bisectrices se cortan sobre la mediana del lado
    LARGO. Si Ly <= Lx el punto de encuentro esta a Ly/2 de cada
    extremo corto, y las vigas largas (las que corren en X) reciben
    trapecios; si no, al reves.

    Es la version geometrica de area_tributaria_viga(): las areas que
    salen de aca deben coincidir con las que calcula esa funcion, y hay
    un test que lo comprueba.
    """
    Lx = x1 - x0
    Ly = y1 - y0
    xm = (x0 + x1) / 2.0
    ym = (y0 + y1) / 2.0

    def area(v):
        """Area de un poligono por la formula del cordonero."""
        a = 0.0
        for i in range(len(v)):
            xa, ya = v[i]
            xb, yb = v[(i + 1) % len(v)]
            a += xa * yb - xb * ya
        return abs(a) / 2.0

    if Ly <= Lx:
        # Las vigas en X son las largas -> trapecio; las Y, triangulo.
        d = Ly / 2.0
        polis = [
            ('y0', 'trapecio',  [(x0, y0), (x1, y0), (x1 - d, ym), (x0 + d, ym)]),
            ('y1', 'trapecio',  [(x0, y1), (x1, y1), (x1 - d, ym), (x0 + d, ym)]),
            ('x0', 'triangulo', [(x0, y0), (x0, y1), (x0 + d, ym)]),
            ('x1', 'triangulo', [(x1, y0), (x1, y1), (x1 - d, ym)]),
        ]
    else:
        d = Lx / 2.0
        polis = [
            ('x0', 'trapecio',  [(x0, y0), (x0, y1), (xm, y1 - d), (xm, y0 + d)]),
            ('x1', 'trapecio',  [(x1, y0), (x1, y1), (xm, y1 - d), (xm, y0 + d)]),
            ('y0', 'triangulo', [(x0, y0), (x1, y0), (xm, y0 + d)]),
            ('y1', 'triangulo', [(x0, y1), (x1, y1), (xm, y1 - d)]),
        ]

    return [{'lado': l, 'forma': f, 'vertices': v, 'area': area(v)}
            for l, f, v in polis]


def w_viga(q, luz_viga, luz_transversal, incluir_peso_vigas=False):
    """
    Carga uniforme equivalente (kN/m) sobre una viga, a partir de la
    carga de superficie q (kN/m2) del pano que soporta.

        w = q * A_tributaria / luz_viga

    Se usa la equivalente que CONSERVA LA CARGA TOTAL (resultante
    estaticamente equivalente), no la que iguala el momento maximo.
    Motivo: la regla 1 del CLAUDE.md exige que el equilibrio cierre con
    error < 1e-6, y solo esta version lo garantiza.

    NOTA para la defensa oral: la carga real sobre la viga es triangular
    o trapezoidal, no uniforme. Repartirla como uniforme conserva la
    resultante pero da un momento y una flecha algo distintos -- esa es
    justamente la diferencia de 0.4% contra SAP2000 documentada en el
    CLAUDE.md. Si algun dia se quiere la forma real, OpenSees no tiene
    -beamTrapezoidal para elasticBeamColumn; habria que discretizar la
    viga en varios elementos o usar -beamPoint.
    """
    A_trib = area_tributaria_viga(luz_viga, luz_transversal)
    w = q * A_trib / luz_viga
    if incluir_peso_vigas:
        w += gamma * A_vig        # peso propio distribuido (kN/m)
    return w


# ============================================================
# 6. SUBDIVISION DE VIGAS
# ============================================================
# Cada viga se modela como varios elementos en serie, con nodos
# intermedios.
#
# POR QUE:
# Unity dibuja cada barra como una recta entre sus dos nodos, asi que
# solo se ve lo que le pasa a los NODOS. Bajo gravedad los 4 nodos de
# techo bajan lo mismo, de modo que las vigas se trasladan pero siguen
# horizontales: la flecha del vano, que ocurre en el centro, no se ve.
#
# Medido en el benchmark:
#     nodo de esquina  -0.06348 mm
#     centro del vano  -0.32963 mm
# El 81% del descenso real quedaba invisible.
#
# Subdividir NO cambia la solucion en los nodos originales (la viga de
# Bernoulli es exacta con un solo elemento): solo agrega puntos donde
# mirar. El numero de oro se mantiene en -0.06348 mm.
#
# Ademas deja casi hechos los diagramas de momento y corte, porque hay
# esfuerzos a lo largo del vano y no solo en los extremos.
#
# Con 1 se vuelve al comportamiento anterior.
SUBDIVISIONES_VIGA = 4

# Topologia de la ultima llamada a construir_modelo(). Se guarda aparte
# para no cambiar la firma de retorno, de la que dependen otros scripts.
ULTIMA_TOPOLOGIA = {
    'centros_vano': [],      # nodos a mitad de cada viga
    'vigas': [],             # [[tags de los sub-elementos de cada viga], ...]
    'nodos_auxiliares': [],  # nodos intermedios creados al subdividir
}


# ============================================================
# 7. CONSTRUCCION DEL MODELO
# ============================================================
def construir_modelo(subdivisiones=None):
    """
    Levanta el modelo en OpenSees desde cero.

    Devuelve (coords, columnas, vigas_x, vigas_y) donde cada lista de
    elementos contiene tuplas (tag, n1, n2) -- se necesitan los nodos
    para exportar el JSON a Unity.

    Las vigas vienen SUBDIVIDIDAS: cada viga aporta varios elementos a
    la lista. Los ids de los nodos originales (1..8) NO cambian; los
    intermedios se numeran despues, para que el nodo 5 siga siendo el
    de esquina contra el que se verifica el numero de oro.
    """
    subdiv = SUBDIVISIONES_VIGA if subdivisiones is None else int(subdivisiones)
    if subdiv < 1:
        raise ValueError(f"subdivisiones debe ser >= 1, vino {subdiv}")
    ops.wipe()
    ops.model('basic', '-ndm', 3, '-ndf', 6)
    ops.uniaxialMaterial('Elastic', 1, Ec)

    ops.geomTransf('Linear', 1, 1, 0, 0)   # columnas
    ops.geomTransf('Linear', 2, 0, 0, 1)   # vigas X
    ops.geomTransf('Linear', 3, 0, 0, 1)   # vigas Y

    coords = {}
    nid = 1
    for iz in range(nNivel):
        for ix in range(nX):
            for iy in range(nY):
                coords[nid] = (X[ix], Y[iy], Z[iz])
                ops.node(nid, X[ix], Y[iy], Z[iz])
                nid += 1

    for i in range(1, nNodosPorPiso + 1):
        ops.fix(i, 1, 1, 1, 1, 1, 1)

    tag = 1
    columnas, vigas_x, vigas_y = [], [], []
    centros_vano, vigas_agrupadas = [], []

    for ix in range(nX):
        for iy in range(nY):
            n1 = 1 + ix * nY + iy
            n2 = 1 + nNodosPorPiso + ix * nY + iy
            ops.element('elasticBeamColumn', tag, n1, n2,
                        A_col, Ec, Gc, J_col, Iy_col, Iz_col, 1)
            columnas.append((tag, n1, n2))
            tag += 1

    # Estado mutable para poder numerar desde la funcion anidada.
    contador = {'nid': nid, 'tag': tag}
    auxiliares = []

    def cadena(nA, nB, transf, destino):
        """Crea los nodos intermedios y los sub-elementos entre nA y nB."""
        pa, pb = coords[nA], coords[nB]
        puntos = [nA]
        for k in range(1, subdiv):
            t = float(k) / subdiv
            p = (pa[0] + (pb[0]-pa[0]) * t,
                 pa[1] + (pb[1]-pa[1]) * t,
                 pa[2] + (pb[2]-pa[2]) * t)
            m = contador['nid']; contador['nid'] += 1
            coords[m] = p
            ops.node(m, *p)
            puntos.append(m)
            auxiliares.append(m)
        puntos.append(nB)

        tags = []
        for a, b in zip(puntos[:-1], puntos[1:]):
            # Inercias CRUZADAS, igual que antes: con vecxz=(0,0,1) el
            # eje local y queda vertical (ver CLAUDE.md).
            t_el = contador['tag']; contador['tag'] += 1
            ops.element('elasticBeamColumn', t_el, a, b,
                        A_vig, Ec, Gc, J_vig, Iz_vig, Iy_vig, transf)
            tags.append(t_el)
            destino.append((t_el, a, b))

        centros_vano.append(puntos[len(puntos) // 2])
        vigas_agrupadas.append(tags)

    for iy in range(nY):
        cadena(1 + nNodosPorPiso + 0 * nY + iy,
               1 + nNodosPorPiso + 1 * nY + iy, 2, vigas_x)

    for ix in range(nX):
        cadena(1 + nNodosPorPiso + ix * nY + 0,
               1 + nNodosPorPiso + ix * nY + 1, 3, vigas_y)

    ULTIMA_TOPOLOGIA['nodos_auxiliares'] = auxiliares
    ULTIMA_TOPOLOGIA['centros_vano'] = centros_vano
    ULTIMA_TOPOLOGIA['vigas'] = vigas_agrupadas
    ULTIMA_TOPOLOGIA['subdivisiones'] = subdiv

    return coords, columnas, vigas_x, vigas_y


def tags(elementos):
    """Extrae solo los tags de una lista de tuplas (tag, n1, n2)."""
    return [t for t, _, _ in elementos]


# ============================================================
# 7. APLICACION DE CARGAS
# ============================================================
def aplicar_carga_distribuida(q, vigas_x, vigas_y, incluir_peso_vigas=False):
    """
    Aplica la carga de losa como distribuida uniforme sobre las vigas.

    Con geomTransf vecxz=(0,0,1), la gravedad va en el 2do componente
    de -beamUniform (Wz local).
        eleLoad('-ele', tag, '-type', '-beamUniform', Wy, Wz, Wx)
    """
    # Vigas que corren en X: su luz es Lx, la transversal es Ly.
    for tag, _, _ in vigas_x:
        w = w_viga(q, Lx, Ly, incluir_peso_vigas)
        ops.eleLoad('-ele', tag, '-type', '-beamUniform', 0.0, -w, 0.0)

    # Vigas que corren en Y: su luz es Ly, la transversal es Lx.
    for tag, _, _ in vigas_y:
        w = w_viga(q, Ly, Lx, incluir_peso_vigas)
        ops.eleLoad('-ele', tag, '-type', '-beamUniform', 0.0, -w, 0.0)


def nuevo_patron_de_carga():
    """Crea el timeSeries + pattern estandar (Plain, lineal)."""
    ops.timeSeries('Linear', 1)
    ops.pattern('Plain', 1, 1)


# ============================================================
# 8. SOLUCION
# ============================================================
def resolver():
    """Analisis estatico lineal. Devuelve 0 si convergio."""
    ops.system('BandGeneral')      # mas robusto que BandSPD con eleLoad
    ops.numberer('RCM')
    ops.constraints('Transformation')
    ops.integrator('LoadControl', 1.0)
    ops.algorithm('Linear')
    ops.analysis('Static')
    ok = ops.analyze(1)
    ops.reactions()
    return ok


# ============================================================
# 9. VALOR DE REFERENCIA (numero de oro del benchmark)
# ============================================================
# Deflexion vertical del nodo de techo bajo carga G.
# Validado contra SAP2000 (-0.06375 mm, diferencia 0.4%).
UZ_TECHO_G_REFERENCIA_MM = -0.06348

# Flecha en el CENTRO del vano bajo G. Es 5 veces mayor que la del nodo
# de esquina: es la deformacion que el visor no mostraba cuando las
# vigas eran un solo elemento.
UZ_CENTRO_VANO_G_REFERENCIA_MM = -0.32963

TOLERANCIA_MM = 1e-4
