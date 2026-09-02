#!/usr/bin/env python3
"""
================================================================
 modelo_v3.py -- el edificio con su GEOMETRIA REAL
================================================================
 Construye el modelo estructural leyendo los planos elemento por
 elemento, con planos_v2.py. No hay grilla inventada: cada pilar,
 viga y muro esta donde el plano lo pone y con la seccion que el
 plano le da.

 Contra el modelo anterior (benchmark_3d.py):

   antes                            ahora
   grilla regular 8x6               pilares donde el plano los muestra
   columnas 50x50 inventadas        P. 70x70, del rotulo del plano
   vigas 30/60 y 30/80 inventadas   V. 60/80, del rotulo del plano
   muros de una sola lamina         muros planta por planta
   base plana                       fundacion escalonada (-7.97 / -4.01)

 NIVELES. Una planta "CIELO PISO N" muestra lo que sostiene esa
 losa: sus pilares son las columnas del piso N (del nivel N-1 al N)
 y sus vigas son las que van EN esa losa.

 Uso:  python modelo_v3.py
================================================================
"""

import math
from collections import Counter, defaultdict

import planos_v2 as pv

# Tolerancia para fundir dos puntos en un mismo nodo. Los pilares
# miden 70 cm, asi que 30 cm no llega a juntar pilares distintos.
TOL_NODO = 0.30

# Material: hormigon G-28, igual que el modelo anterior.
FPC = 28.0
EC = 4700.0 * math.sqrt(FPC) * 1000.0     # kPa
GC = EC / (2.0 * (1.0 + 0.2))
GAMMA = 25.0

# Seccion por defecto cuando el plano no la rotula. Son los tipos
# dominantes, contados de los rotulos de RLE-TEXTO-1.
VIGA_CANTO_DEF = 0.80      # "V. 60/80" es el rotulo mas repetido
LOSA_T = 0.25
TERMINACIONES = 1.5        # kN/m2
SOBRECARGA = 2.0           # kN/m2

# Cota del radier dominante en la planta de fundaciones. El plano trae
# varios N.R. porque la fundacion es escalonada: -7.97 manda y -4.01
# es el escalon del oriente.
COTA_FUNDACION = -7.97


def J_rectangular(b, h):
    """Saint-Venant para rectangulo lleno. a = lado largo, t = corto."""
    a, t = max(b, h), min(b, h)
    return a * t**3 * (1.0 / 3.0 - 0.21 * (t / a) * (1.0 - t**4 / (12 * a**4)))


# ================================================================
# LECTURA DE LOS PLANOS
# ================================================================
def leer_planos():
    """
    Los niveles del edificio, de abajo hacia arriba, cada uno con sus
    pilares, vigas y muros ya llevados al sistema comun.
    """
    niveles = []
    for pl in pv.todas_las_plantas():
        off = (pl['dx'], pl['dy'])
        niveles.append({
            'titulo': pl['titulo'],
            'cota': pl['cota'],
            'pilares': pv.pilares(pl['hoja'], pl, off),
            'vigas': pv.vigas(pl['hoja'], pl, off),
            'muros': pv.muros(pl['hoja'], pl, off),
        })
    return niveles


# ================================================================
# NODOS
# ================================================================
class Nodos:
    """
    Registro de nodos que funde los puntos cercanos.

    Sin esto cada viga traeria sus propios extremos y la estructura
    quedaria desconectada: dos barras que se cruzan sin compartir nodo
    no se transmiten nada.
    """

    def __init__(self, tol=TOL_NODO):
        self.tol = tol
        self.coords = {}          # id -> (x, y, z)
        self._rejilla = defaultdict(list)
        self._sig = 1

    def _celda(self, x, y, z):
        t = self.tol
        return (round(x / t), round(y / t), round(z / t))

    def obtener(self, x, y, z):
        """Id del nodo en (x,y,z), creandolo si no habia uno cerca."""
        cx, cy, cz = self._celda(x, y, z)
        mejor, mejor_d = None, None
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for nid in self._rejilla.get((cx + dx, cy + dy, cz), []):
                    px, py, pz = self.coords[nid]
                    if abs(pz - z) > 1e-6:
                        continue
                    d = math.hypot(px - x, py - y)
                    if d <= self.tol and (mejor_d is None or d < mejor_d):
                        mejor, mejor_d = nid, d
        if mejor is not None:
            return mejor
        nid = self._sig
        self._sig += 1
        self.coords[nid] = (x, y, z)
        self._rejilla[(cx, cy, cz)].append(nid)
        return nid


# Cuanto se puede estirar el extremo de una viga para engancharlo a
# su apoyo. Las vigas del plano llegan a la CARA del pilar, no a su
# eje: con pilares de 70 cm el retranqueo es 0.35 m, y contra otra
# viga de 60 cm es 0.30 m. 0.80 m cubre ambos con holgura sin llegar
# al apoyo siguiente.
RADIO_ENGANCHE = 0.80


def eje_de_muro(m):
    """Punto medio del muro: donde va su barra equivalente."""
    if m['dir'] == 'X':
        return ((m['ini'] + m['fin']) / 2.0, m['coord'])
    return (m['coord'], (m['ini'] + m['fin']) / 2.0)


def mallar(vigas, pilares_xy, tol=TOL_NODO):
    """
    Deja la reticula de vigas de un nivel CONECTADA.

    Hace dos cosas, y las dos son necesarias:

    1. ENGANCHA los extremos. En el plano las vigas terminan en la
       CARA del pilar o de la viga que las recibe, no en su eje: una
       viga entre pilares de 70 cm a 55.20 y 64.10 se dibuja de 55.55
       a 63.75. Si se toma tal cual, no toca nada y queda flotando.
       El modelo de barras trabaja con ejes, asi que cada extremo se
       estira hasta el eje de apoyo mas cercano.

    2. PARTE la viga en sus cruces con las perpendiculares y en los
       pilares intermedios, para que compartan nodo.

    Devuelve [(dir, coord, ini, fin, ancho)] con los subtramos.
    """
    enX = [v for v in vigas if v['dir'] == 'X']
    enY = [v for v in vigas if v['dir'] == 'Y']

    def ejes_apoyo(v, perpendiculares):
        """
        Coordenadas longitudinales donde v tiene un apoyo: ejes de
        vigas perpendiculares y centros de pilar alineados con ella.
        """
        ejes = [w['coord'] for w in perpendiculares]
        for px, py in pilares_xy:
            largo_p, trans_p = (px, py) if v['dir'] == 'X' else (py, px)
            if abs(trans_p - v['coord']) <= 1.0:
                ejes.append(largo_p)
        return ejes

    def enganchar(valor, ejes):
        """Lleva un extremo al eje de apoyo mas cercano, si esta cerca."""
        cerca = [e for e in ejes if abs(e - valor) <= RADIO_ENGANCHE]
        return min(cerca, key=lambda e: abs(e - valor)) if cerca else valor

    out = []
    for grupo, perp, dir_ in ((enX, enY, 'X'), (enY, enX, 'Y')):
        for v in grupo:
            ejes = ejes_apoyo(v, perp)
            a = enganchar(v['ini'], ejes)
            b = enganchar(v['fin'], ejes)
            if b - a < tol:
                continue

            # Cortes: los apoyos que caen DENTRO del tramo ya estirado.
            ptos = sorted({a, b} | {e for e in ejes if a + tol < e < b - tol})
            limpios = [ptos[0]]
            for q in ptos[1:]:
                if q - limpios[-1] > tol:
                    limpios.append(q)
            for i in range(len(limpios) - 1):
                out.append((dir_, v['coord'], limpios[i], limpios[i + 1],
                            v['espesor']))
    return out


def construir():
    """Arma nodos y elementos del edificio a partir de los planos."""
    niveles = leer_planos()
    con_geom = [n for n in niveles if n['cota'] is not None]
    cotas = [COTA_FUNDACION] + [n['cota'] for n in con_geom]

    nod = Nodos()
    elementos = []      # (tipo, n1, n2, datos)

    # --- Columnas ---
    # Un pilar de la planta "cielo N" es la columna del piso N, que va
    # del nivel N-1 al N. Se PROLONGA HACIA ABAJO hasta la base: una
    # columna no flota, y las plantas de subterraneo no dibujan sus
    # pilares en RLE-PILAR (el 1o subterraneo trae cero).
    por_pos = {}
    for k, niv in enumerate(con_geom, start=1):
        for q in niv['pilares']:
            clave = (round(q['x'] / TOL_NODO), round(q['y'] / TOL_NODO))
            c = por_pos.get(clave)
            if c is None:
                por_pos[clave] = {'x': q['x'], 'y': q['y'],
                                  'bx': q['bx'], 'by': q['by'], 'hasta': k}
            else:
                c['hasta'] = max(c['hasta'], k)

    for c in por_pos.values():
        for k in range(1, c['hasta'] + 1):
            n1 = nod.obtener(c['x'], c['y'], cotas[k - 1])
            n2 = nod.obtener(c['x'], c['y'], cotas[k])
            elementos.append(('columna', n1, n2,
                              {'b': c['bx'], 'h': c['by'], 'nivel': k}))

    muros_por_pos = {}

    # --- Vigas ---
    # Hay que MALLAR: las vigas del DXF son tramos sueltos que no se
    # cortan entre si ni llegan a los pilares. Sin partirlas en sus
    # cruces, cada viga queda como una barra aislada y la estructura
    # no transmite nada (496 de 632 nodos con un solo elemento).
    for k, niv in enumerate(con_geom, start=1):
        z = cotas[k]
        # Puntos de apoyo del nivel: los pilares que llegan hasta aca
        # MAS el eje de cada muro. El muro se modela como columna
        # ancha, asi que para la reticula es un apoyo mas; sin
        # incluirlo su nodo queda flotando y no recibe nada de las
        # vigas que deberia estar sosteniendo.
        pil = [(c['x'], c['y']) for c in por_pos.values()
               if c['hasta'] >= k]
        pil += [eje_de_muro(mu) for mu in niv['muros']]
        for dir_, coord, ini, fin, ancho in mallar(niv['vigas'], pil):
            if dir_ == 'X':
                a = nod.obtener(ini, coord, z)
                b = nod.obtener(fin, coord, z)
            else:
                a = nod.obtener(coord, ini, z)
                b = nod.obtener(coord, fin, z)
            if a != b:
                elementos.append(('viga_' + dir_.lower(), a, b,
                                  {'b': ancho, 'h': VIGA_CANTO_DEF,
                                   'nivel': k}))
        # Los muros se acumulan por posicion y se generan despues:
        # hay que PROLONGARLOS HACIA ABAJO hasta la base, igual que
        # las columnas. Un muro que arranca en un nivel intermedio sin
        # nada debajo queda colgando: el primer intento dio 751 mm de
        # descenso en un muro suspendido entre -4.01 y -0.05.
        for mu in niv['muros']:
            xm, ym = eje_de_muro(mu)
            clave = (round(xm / TOL_NODO), round(ym / TOL_NODO))
            c = muros_por_pos.get(clave)
            if c is None:
                muros_por_pos[clave] = {'x': xm, 'y': ym, 'hasta': k,
                                        'largo': mu['largo'],
                                        'espesor': mu['espesor'],
                                        'dir': mu['dir']}
            else:
                c['hasta'] = max(c['hasta'], k)
                c['largo'] = max(c['largo'], mu['largo'])

    # Muros: desde la base hasta donde el plano los muestra.
    for c in muros_por_pos.values():
        for k in range(1, c['hasta'] + 1):
            n1 = nod.obtener(c['x'], c['y'], cotas[k - 1])
            n2 = nod.obtener(c['x'], c['y'], cotas[k])
            if n1 != n2:
                elementos.append(('muro', n1, n2,
                                  {'largo': c['largo'],
                                   'espesor': c['espesor'],
                                   'dir': c['dir'], 'nivel': k}))

    # --- Brazos rigidos muro -> reticula ---
    # El muro va como COLUMNA ANCHA: una barra en su eje. Pero su eje
    # cae en el punto medio del muro, donde no tiene por que pasar una
    # viga, asi que su nodo queda flotando y el muro no recibe nada.
    #
    # Se une con brazos rigidos a los nodos de la reticula que caen
    # SOBRE el muro, en su misma cota. Es el mecanismo que el servidor
    # ya soporta ("brazos_rigidos") y lo que le da ancho al muro: sin
    # esto se comporta como si tuviera espesor cero.
    brazos = []
    for k, niv in enumerate(con_geom, start=1):
        for m in niv['muros']:
            xm, ym = eje_de_muro(m)
            for z in (cotas[k - 1], cotas[k]):
                maestro = nod.obtener(xm, ym, z)
                for nid, (x, y, zz) in nod.coords.items():
                    if nid == maestro or abs(zz - z) > 1e-6:
                        continue
                    if m['dir'] == 'X':
                        sobre = (abs(y - m['coord']) <= 0.6
                                 and m['ini'] - 0.1 <= x <= m['fin'] + 0.1)
                    else:
                        sobre = (abs(x - m['coord']) <= 0.6
                                 and m['ini'] - 0.1 <= y <= m['fin'] + 0.1)
                    if sobre:
                        brazos.append((maestro, nid))

    # Un brazo rigido condensa los DOF del esclavo en el maestro, y eso
    # impone tres reglas que OpenSees no perdona: la matriz sale
    # SINGULAR y el analisis muere sin decir por que.
    #
    #   1. Un esclavo no puede serlo de dos maestros.
    #   2. Un nodo no puede ser maestro y esclavo a la vez (cadenas).
    #   3. Un esclavo no puede estar EMPOTRADO: sus DOF ya no le
    #      pertenecen, asi que el apoyo y el vinculo se pelean.
    #
    # Las tres se dieron al generar los brazos automaticamente: 5
    # nodos salieron maestro y esclavo, y 6 esclavos caian en la base.
    en_base = {nid for nid, (_x, _y, z) in nod.coords.items()
               if abs(z - cotas[0]) < 1e-6}
    todos_maestros = {ma for ma, _e in brazos}

    vistos, limpios = set(), []
    for maestro, esclavo in brazos:
        if (esclavo == maestro or esclavo in vistos
                or esclavo in en_base or esclavo in todos_maestros):
            continue
        vistos.add(esclavo)
        limpios.append((maestro, esclavo))

    elementos, limpios, podados = podar(nod, elementos, limpios, cotas[0])
    return nod, elementos, cotas, con_geom, limpios, podados


def podar(nod, elementos, brazos, cota_base):
    """
    Quita lo que NO tiene camino a un apoyo.

    Un grupo de barras flotando deja la matriz de rigidez SINGULAR y
    OpenSees muere con "matrix singular U(i,i)=0", sin decir donde. Son
    tramos que el DXF trae sueltos -- escaleras, elementos secundarios,
    vigas cuyo apoyo quedo fuera del pareo -- y que no llegan a
    engancharse con nada.

    Devuelve (elementos, brazos, podados) y NO los descarta en
    silencio: 'podados' se reporta.
    """
    ady = defaultdict(set)
    for _t, a, b, _d in elementos:
        ady[a].add(b)
        ady[b].add(a)
    for ma, es in brazos:
        ady[ma].add(es)
        ady[es].add(ma)

    base = [nid for nid, (_x, _y, z) in nod.coords.items()
            if abs(z - cota_base) < 1e-6]
    vivos, pila = set(base), list(base)
    while pila:
        u = pila.pop()
        for v in ady[u]:
            if v not in vivos:
                vivos.add(v)
                pila.append(v)

    ok_el = [e for e in elementos if e[1] in vivos and e[2] in vivos]
    ok_br = [b for b in brazos if b[0] in vivos and b[1] in vivos]
    podados = {
        'nodos': len(nod.coords) - len(vivos),
        'elementos': len(elementos) - len(ok_el),
        'brazos': len(brazos) - len(ok_br),
    }
    # Los nodos que quedan fuera se borran para que no aparezcan
    # sueltos en el modelo ni en el export a Unity.
    for nid in list(nod.coords):
        if nid not in vivos:
            del nod.coords[nid]
    return ok_el, ok_br, podados


def main():
    nod, elementos, cotas, niveles, brazos, podados = construir()
    print("COTAS DE LOSA (m):", [round(c, 2) for c in cotas])
    alturas = [round(cotas[i + 1] - cotas[i], 2) for i in range(len(cotas) - 1)]
    print(f"  alturas de piso: {alturas}")

    print(f"\nNODOS: {len(nod.coords)}")
    tipos = Counter(t for t, _a, _b, _d in elementos)
    print(f"ELEMENTOS: {len(elementos)}")
    for t, n in tipos.most_common():
        print(f"    {t:10s} {n}")

    print("\nPor nivel:")
    for k, niv in enumerate(niveles, start=1):
        c = Counter(t for t, _a, _b, d in elementos if d.get('nivel') == k)
        print(f"  {k}  z={cotas[k]:+6.2f}  {niv['titulo'][:30]:30s} "
              f"col {c.get('columna', 0):3d}  "
              f"vigas {c.get('viga_x', 0) + c.get('viga_y', 0):3d}  "
              f"muros {c.get('muro', 0):3d}")

    print("")
    print(f"BRAZOS RIGIDOS muro->reticula: {len(brazos)}")
    print(f"PODADO (sin camino a un apoyo): {podados['nodos']} nodos, "
          f"{podados['elementos']} elementos, {podados['brazos']} brazos")

    secc = Counter((round(d['b'], 2), round(d['h'], 2))
                   for t, _a, _b, d in elementos if t == 'columna')
    print("\nSecciones de columna:", dict(secc))


if __name__ == '__main__':
    main()


# ================================================================
# RESOLUCION EN OPENSEES
# ================================================================
def propiedades(tipo, d):
    """
    (A, Iy, Iz, J, vecxz) de un elemento, en la convencion del
    contrato del proyecto: Iz es la inercia de GRAVEDAD (la del
    canto) e Iy la lateral. El cruce al llamar a 'element' lo hace
    quien arma el modelo, segun si el elemento es vertical.
    """
    if tipo == 'muro':
        b, h = d['espesor'], d['largo']
        vec = (1.0, 0.0, 0.0) if d['dir'] == 'X' else (0.0, 1.0, 0.0)
        A = b * h
        # El eje FUERTE del muro esta en su plano: es el que lleva el
        # largo al cubo, y va en Iy porque el muro es vertical.
        return A, b * h**3 / 12.0, h * b**3 / 12.0, J_rectangular(b, h), vec

    b, h = d['b'], d['h']
    A = b * h
    Iz = b * h**3 / 12.0        # gravedad: la del canto
    Iy = h * b**3 / 12.0        # lateral
    return A, Iy, Iz, J_rectangular(b, h), None


def resolver(verbose=True):
    """
    Arma el modelo en OpenSees, le aplica el peso propio y resuelve.

    Verifica el equilibrio: la suma de reacciones tiene que dar la
    carga aplicada. Es el chequeo que pilla cargas perdidas.
    """
    import openseespy.opensees as ops

    nod, elementos, cotas, niveles, brazos, podados = construir()

    ops.wipe()
    ops.model('basic', '-ndm', 3, '-ndf', 6)

    for nid, (x, y, z) in nod.coords.items():
        ops.node(nid, x, y, z)

    # Apoyos: todo lo que llega a la cota de fundacion.
    base = [nid for nid, (_x, _y, z) in nod.coords.items()
            if abs(z - cotas[0]) < 1e-6]
    for nid in base:
        ops.fix(nid, 1, 1, 1, 1, 1, 1)

    # Transformaciones: una por vecxz distinto.
    transf, sig_t = {}, [1]

    def tag_transf(vec):
        if vec not in transf:
            transf[vec] = sig_t[0]
            ops.geomTransf('Linear', sig_t[0], *vec)
            sig_t[0] += 1
        return transf[vec]

    peso = 0.0
    cargas = defaultdict(float)      # nodo -> kN hacia abajo

    for tag, (tipo, n1, n2, d) in enumerate(elementos, start=1):
        x1, y1, z1 = nod.coords[n1]
        x2, y2, z2 = nod.coords[n2]
        L = math.dist((x1, y1, z1), (x2, y2, z2))
        if L < 1e-6:
            continue

        A, Iy, Iz, J, vec = propiedades(tipo, d)
        vertical = abs(z2 - z1) > 0.99 * L

        if vec is None:
            vec = (1.0, 0.0, 0.0) if vertical else (0.0, 0.0, 1.0)

        # El cruce de inercias es SOLO para los no verticales: con
        # vecxz=(0,0,1) el eje local z queda vertical, asi que la
        # flexion por gravedad ocurre alrededor del eje local y.
        if vertical:
            Iy_pass, Iz_pass = Iy, Iz
        else:
            Iy_pass, Iz_pass = Iz, Iy

        ops.element('elasticBeamColumn', tag, n1, n2,
                    A, EC, GC, J, Iy_pass, Iz_pass, tag_transf(vec))

        # Peso propio, mitad a cada extremo.
        W = GAMMA * A * L
        peso += W
        cargas[n1] += W / 2.0
        cargas[n2] += W / 2.0

    for maestro, esclavo in brazos:
        ops.rigidLink('beam', maestro, esclavo)

    # --- Caso G: peso propio ---
    ops.timeSeries('Linear', 1)
    ops.pattern('Plain', 1, 1)
    aplicado = 0.0
    for nid, W in cargas.items():
        if nid in base:
            continue          # lo que cuelga del apoyo no entra
        ops.load(nid, 0.0, 0.0, -W, 0.0, 0.0, 0.0)
        aplicado += W

    ops.system('BandGeneral')
    ops.numberer('RCM')
    ops.constraints('Transformation')
    ops.integrator('LoadControl', 1.0)
    ops.algorithm('Linear')
    ops.analysis('Static')
    ok = ops.analyze(1)

    ops.reactions()
    Rz = sum(ops.nodeReaction(nid, 3) for nid in base)
    uz = min(ops.nodeDisp(nid, 3) for nid in nod.coords)

    if verbose:
        print(f"nodos {len(nod.coords)}   elementos {len(elementos)}   "
              f"brazos {len(brazos)}   apoyos {len(base)}")
        print(f"convergencia: {'OK' if ok == 0 else 'FALLO'}")
        print(f"peso propio total       : {peso:12.2f} kN")
        print(f"  aplicado (sin apoyos) : {aplicado:12.2f} kN")
        print(f"  suma de reacciones    : {Rz:12.2f} kN")
        print(f"  error de equilibrio   : {abs(aplicado - Rz):12.6f} kN")
        print(f"UZ maximo (descenso)    : {uz*1000:12.4f} mm")
    return ok, aplicado, Rz, uz
