# -*- coding: utf-8 -*-
r"""
================================================================
 comun/capacidad.py  -  QUE AGUANTA UNA SECCION
================================================================
 Momento-curvatura y curva de interaccion P-M de una seccion de
 hormigon armado, con Fiber Section de OpenSees.

 Correr:
   python comun/capacidad.py lt2 1          la columna del elemento 1
   python comun/capacidad.py lt2 9          un muro
   python comun/capacidad.py lt2 1 --pm     ademas su curva P-M
   python comun/capacidad.py lt2 1 --sensibilidad

 Sirve para los dos: una columna es una seccion cuadrada con
 armadura perimetral y un muro una seccion muy alargada con malla
 repartida mas barras en las puntas. Lo que cambia es como se arman
 las fibras, no el analisis. Ver _seccion_de_muro().

 ----------------------------------------------------------------
 UNA SOLA DEFINICION DE LA SECCION
 ----------------------------------------------------------------
 El M-phi y la P-M salen del MISMO objeto de fibras. Es la razon de
 que la P-M se calcule corriendo un M-phi por cada nivel de carga
 axial y quedarse con el momento maximo, en vez de integrar aparte
 con una ley escrita a mano en Python.

 Integrar aparte es mas rapido, pero deja dos definiciones de la
 misma seccion que hay que mantener sincronizadas: distinta
 discretizacion, distinta ley del hormigon, distinto numero de
 barras. Cuando se separan, el M-phi y la P-M dejan de ser de la
 misma columna y nadie lo nota, porque los dos graficos siguen
 saliendo con forma razonable.

 Ademas asi el punto de la P-M tiene una definicion que se puede
 explicar en una frase: es el momento maximo que alcanza la seccion
 con esa compresion.

 ----------------------------------------------------------------
 DE DONDE SALE CADA NUMERO
 ----------------------------------------------------------------
 La seccion se lee del modelo, no se escribe aca:

     b, h            de la seccion del elemento    (data/modelo)
     f'c             del material del modelo       (35 MPa en el LT2)
     estribo, trabas de la elevacion del plano     (enfierradura.py)
     n de barras     deducido del estribo          (una traba amarra
                                                    una barra)
     diametro        SUPUESTO, declarado en el perfil

 El confinamiento NO es un numero puesto a mano: sale del estribo
 que trae el elemento, con Mander. Por eso las dos familias de
 columnas del LT2 -- las de 3 trabas y las de 4 -- dan curvas
 distintas, que es justamente lo que hay que poder mostrar.

 ----------------------------------------------------------------
 UNIDADES
 ----------------------------------------------------------------
 Todo en m, kN, kPa, como el resto del proyecto. f'c = 35 MPa son
 35000 kPa. Los momentos salen en kN*m y las curvaturas en 1/m.
================================================================
"""
from __future__ import annotations

import math
import os
import sys

_AQUI = os.path.dirname(os.path.abspath(__file__))
if _AQUI not in sys.path:
    sys.path.insert(0, _AQUI)

import contrato                              # noqa: E402
import rutas                                 # noqa: E402

# --- discretizacion por defecto -------------------------------
# Fibras a lo alto del nucleo. 20 basta: la sensibilidad esta
# verificada en sensibilidad_discretizacion() y entre 20 y 40 el
# momento maximo cambia menos de 0.5%.
FIBRAS_NUCLEO = 20
FIBRAS_RECUBRIMIENTO = 4

# --- deformaciones caracteristicas ----------------------------
EPS_C0 = 0.002          # hormigon no confinado, peak
EPS_CU_RECUBRIMIENTO = 0.004
EPS_SU = 0.10           # rotura del acero (A630-420H, alargamiento)

# Deformacion ultima del hormigon que usa ACI 318 para definir la
# resistencia NOMINAL de la seccion. No es la deformacion a la que la
# seccion se rompe -- con el nucleo confinado llega mucho mas lejos --
# sino la convencion con la que se calcula a mano y con la que estan
# hechas las tablas del curso de hormigon armado.
EPS_C_ACI = 0.003

# ke de Mander para seccion rectangular con estribos y trabas.
# 0.75 es el valor tipico; con muchas trabas sube, con pocas baja.
KE_CONFINAMIENTO = 0.75

# --- analisis -------------------------------------------------
# Paso de curvatura para una seccion de 0.70 m de canto. Para otra
# altura se escala: la curvatura de rotura va como 1/h, asi que un
# muro de 7.95 m fluye a curvaturas once veces menores y con el paso
# de la columna la curva sale de diez puntos.
PASO_CURVATURA = 1.0e-4     # 1/m, referido a CANTO_REFERENCIA
CANTO_REFERENCIA = 0.70     # m
PASOS_MAXIMOS = 2500


def paso_para(sec):
    """Paso de curvatura proporcionado al canto de la seccion."""
    return PASO_CURVATURA * CANTO_REFERENCIA / max(sec.h, 0.10)


class Seccion(object):
    """Una seccion de hormigon armado, con todo lo que hace falta."""

    def __init__(self, nombre, b, h, fpc_kPa, barras, recubrimiento,
                 fy_kPa, Es_kPa, endurecimiento, estribo=None,
                 trabas_x=0, trabas_y=0, origen=None):
        self.nombre = nombre
        self.b = float(b)                  # ancho, direccion z local
        self.h = float(h)                  # canto, direccion y local
        self.fpc = float(fpc_kPa)
        self.barras = barras               # [(y, z, area_m2), ...]
        self.rec = float(recubrimiento)
        self.fy = float(fy_kPa)
        self.Es = float(Es_kPa)
        self.endurecimiento = float(endurecimiento)
        self.estribo = estribo or {}
        self.trabas_x = int(trabas_x)
        self.trabas_y = int(trabas_y)
        self.origen = origen or {}

    # --- geometria ---------------------------------------------
    @property
    def Ag(self):
        return self.b * self.h

    @property
    def As(self):
        return sum(a for _y, _z, a in self.barras)

    @property
    def cuantia(self):
        return self.As / self.Ag if self.Ag else 0.0

    def nucleo(self):
        """(alto, ancho) del nucleo, medido al EJE del estribo."""
        d = self._diametro_estribo()
        return (self.h - 2 * self.rec - d, self.b - 2 * self.rec - d)

    def _diametro_estribo(self):
        return float(self.estribo.get('diametro_mm', 0.0)) / 1000.0

    # --- confinamiento (Mander) --------------------------------
    def confinamiento(self):
        r"""
        Presion de confinamiento y hormigon confinado, por Mander.

        No es un factor puesto a mano: sale del estribo que el plano
        le pone a ESTE elemento. Un pilar con 4 trabas tiene mas
        ramas que uno con 3, mas presion lateral, y por lo tanto mas
        f'cc y mucha mas deformacion ultima. Es la diferencia que se
        tiene que ver entre las dos familias de columnas del LT2.

        Devuelve un dict con todo lo intermedio, para poder mostrarlo
        y para que se pueda revisar a mano.
        """
        d = self._diametro_estribo()
        s = float(self.estribo.get('separacion_cm', 0.0)) / 100.0
        hc, bc = self.nucleo()
        if min(d, s, hc, bc) <= 0:
            return None

        a_barra = math.pi * d ** 2 / 4.0
        # Ramas que cruzan cada direccion: las dos del estribo mas una
        # por cada traba.
        ramas_x = 2 + self.trabas_x
        ramas_y = 2 + self.trabas_y
        Ash_x = ramas_x * a_barra
        Ash_y = ramas_y * a_barra

        rho_x = Ash_x / (s * bc)
        rho_y = Ash_y / (s * hc)
        fl_x = KE_CONFINAMIENTO * rho_x * self.fy
        fl_y = KE_CONFINAMIENTO * rho_y * self.fy
        fl = (fl_x + fl_y) / 2.0

        # Mander para confinamiento igual en las dos direcciones.
        r = fl / self.fpc
        K = -1.254 + 2.254 * math.sqrt(1.0 + 7.94 * r) - 2.0 * r
        fcc = K * self.fpc
        eps_cc = EPS_C0 * (1.0 + 5.0 * (K - 1.0))

        # Deformacion ultima del nucleo (Priestley): el nucleo se
        # rompe cuando se corta el estribo.
        rho_s = rho_x + rho_y
        eps_cu = 0.004 + 1.4 * rho_s * self.fy * EPS_SU / fcc

        return {
            'ramas_x': ramas_x, 'ramas_y': ramas_y,
            'rho_x': rho_x, 'rho_y': rho_y, 'rho_s': rho_s,
            'fl_kPa': fl, 'K': K,
            'fcc_kPa': fcc, 'eps_cc': eps_cc, 'eps_cu': eps_cu,
            'nucleo_m': (hc, bc), 'separacion_m': s,
        }

    def resumen(self):
        c = self.confinamiento()
        L = ['%s   %.2f x %.2f m' % (self.nombre, self.b, self.h),
             '  hormigon   f\'c = %.1f MPa' % (self.fpc / 1000.0),
             '  acero      fy  = %.0f MPa, Es = %.0f GPa'
             % (self.fy / 1000.0, self.Es / 1e6),
             '  refuerzo   %d barras, As = %.2f cm2, cuantia = %.2f %%'
             % (len(self.barras), self.As * 1e4, 100 * self.cuantia),
             '  estribo    %s' % (self.estribo.get('texto', '(sin dato)')),
             '  trabas     %d en x, %d en y' % (self.trabas_x, self.trabas_y)]
        if c:
            L.append('  confinado  f\'cc = %.1f MPa (K = %.3f), '
                     'eps_cc = %.5f, eps_cu = %.5f'
                     % (c['fcc_kPa'] / 1000.0, c['K'], c['eps_cc'],
                        c['eps_cu']))
        return '\n'.join(L)


# ============================================================
# LEER LA SECCION DESDE EL MODELO
# ============================================================
def desde_elemento(modelo, elemento_id):
    """
    La seccion del elemento tal como la describe el modelo, con la
    enfierradura que se le pego en la etapa de armado.

    Falla con un mensaje explicito si el elemento no trae fierro: una
    seccion de hormigon armado sin armadura no es una seccion con
    armadura cero, es un dato que falta.
    """
    elementos = {int(e['id']): e for e in modelo['elementos']}
    if int(elemento_id) not in elementos:
        raise SystemExit('el elemento %s no existe en el modelo'
                         % elemento_id)
    e = elementos[int(elemento_id)]

    fe = e.get('enfierradura')
    if not fe:
        raise SystemExit(
            'el elemento %s (%s) no trae enfierradura.\n'
            'Se le pega en edificios/lt2/armar.py desde la elevacion del '
            'plano; no todos los muros tienen su elevacion leida.'
            % (elemento_id, e.get('tipo')))

    if fe.get('tipo') == 'muro':
        return _seccion_de_muro(modelo, e, fe, elemento_id)

    secciones = {s['nombre']: s for s in modelo['secciones']}
    s = secciones.get(e.get('seccion'))
    if not s:
        raise SystemExit('el elemento %s usa la seccion %r, que no esta '
                         'declarada' % (elemento_id, e.get('seccion')))

    b, h = float(s['b']), float(s['h'])
    fpc = float(modelo['material']['fpc_MPa']) * 1000.0
    acero = fe.get('acero') or {}
    fy = float(acero.get('fy_MPa', 420.0)) * 1000.0
    Es = float(acero.get('Es_MPa', 200000.0)) * 1000.0
    endur = float(acero.get('endurecimiento', 0.01))

    lon = fe['longitudinal']
    rec = float(fe.get('recubrimiento_m', 0.04))
    d_estribo = float((fe.get('estribo') or {}).get('diametro_mm', 0)) / 1000.0
    d_barra = float(lon['diametro_mm']) / 1000.0
    barras = _perimetral(b, h, rec + d_estribo + d_barra / 2.0,
                         int(lon['por_cara']), d_barra)

    trabas = sum(t['cantidad'] for t in (fe.get('trabas') or []))
    trabas_l = sum(t['cantidad'] for t in (fe.get('trabas_longitudinales') or []))

    return Seccion(
        nombre='%s (elem %s)' % (e['seccion'], elemento_id),
        b=b, h=h, fpc_kPa=fpc, barras=barras, recubrimiento=rec,
        fy_kPa=fy, Es_kPa=Es, endurecimiento=endur,
        estribo=fe.get('estribo'), trabas_x=trabas, trabas_y=trabas_l,
        origen=fe.get('fuente') or {})


def _seccion_de_muro(modelo, e, fe, elemento_id, recubrimiento=0.03):
    r"""
    La seccion de un muro, para flexion EN SU PLANO.

    ----------------------------------------------------------------
    QUE ES b Y QUE ES h EN UN MURO
    ----------------------------------------------------------------
    Al reves de lo que uno diria: h -- el canto, la direccion en que
    la seccion es alta -- es el LARGO del muro, porque es en ese plano
    donde flecta cuando lo empuja el sismo. b es el espesor. Un muro
    de 0.25 x 7.95 es entonces una seccion de 25 cm de ancho y 7.95 m
    de canto: por eso su capacidad a flexion en el plano es enorme y
    fuera del plano, ridicula.

    Se calcula solo la direccion principal, que es la que pide el
    enunciado y la unica que tiene sentido comparar: fuera del plano
    el muro no toma sismo, lo toman los muros perpendiculares.

    ----------------------------------------------------------------
    DOS FAMILIAS DE FIERRO
    ----------------------------------------------------------------
    MALLA repartida a lo largo de todo el muro, en DOS cortinas -- una
    por cara -- que es lo que significa 'D.M.' en el plano. Aporta poco
    a la flexion: casi toda esta cerca del eje neutro.

    BARRAS DE BORDE en las puntas, donde el brazo de palanca es
    maximo. Son las que mandan. Se colocan en la posicion que el plano
    les da, medida desde el centro del muro -- ponerlas al medio daria
    una capacidad muy por debajo de la real.

    ----------------------------------------------------------------
    EL HORMIGON VA SIN CONFINAR
    ----------------------------------------------------------------
    El alma de un muro no tiene estribos, y aunque el plano confina
    las puntas -- se ve el '(CONF.)' con su E%%C12a10 -- ese dato no
    esta asociado muro por muro todavia. Sin confinamiento la seccion
    llega a menos deformacion y da MENOS capacidad, asi que el
    resultado queda del lado seguro.
    """
    secciones = {s['nombre']: s for s in modelo['secciones']}
    s = secciones.get(e.get('seccion'))
    t = float(fe.get('espesor_m') or (s and s['b']) or 0.0)
    L = float(fe.get('largo_m') or (s and s['h']) or 0.0)
    fpc = float(modelo['material']['fpc_MPa']) * 1000.0

    mv = fe.get('malla_vertical') or {}
    capas = int(fe.get('capas', 2))
    barras = []

    # --- la malla, repartida a lo largo del muro ---
    d_malla = float(mv.get('diametro_mm', 0.0)) / 1000.0
    sep = float(mv.get('separacion_cm', 0.0)) / 100.0
    z_capa = max(t / 2.0 - recubrimiento - d_malla / 2.0, 0.0)
    if d_malla > 0 and sep > 0:
        a = math.pi * d_malla ** 2 / 4.0
        n = int(L / sep)
        for i in range(n + 1):
            y = -L / 2.0 + i * sep
            if abs(y) > L / 2.0:
                continue
            for z in ((-z_capa, z_capa) if capas >= 2 else (0.0,)):
                barras.append((y, z, a))

    # --- las barras de borde, en su sitio ---
    for b in fe.get('barras_de_borde') or []:
        d = float(b['diametro_mm']) / 1000.0
        a = math.pi * d ** 2 / 4.0
        y = max(-L / 2.0, min(L / 2.0, float(b['s'])))
        n = int(b.get('cantidad', 1))
        # Repartidas entre las dos cortinas, como van en la punta.
        for k in range(n):
            z = z_capa if k % 2 == 0 else -z_capa
            barras.append((y, z, a))

    acero = {'fy_MPa': 420.0, 'Es_MPa': 200000.0, 'endurecimiento': 0.01}
    return Seccion(
        nombre='%s (muro, elem %s)' % (e['seccion'], elemento_id),
        b=t, h=L, fpc_kPa=fpc, barras=barras, recubrimiento=recubrimiento,
        fy_kPa=acero['fy_MPa'] * 1000.0, Es_kPa=acero['Es_MPa'] * 1000.0,
        endurecimiento=acero['endurecimiento'],
        estribo=None, trabas_x=0, trabas_y=0,
        origen=dict(fe.get('fuente') or {},
                    malla=mv.get('texto'),
                    barras_de_borde=len(fe.get('barras_de_borde') or [])))


def _perimetral(b, h, d, por_cara, diam):
    """
    Barras repartidas en el perimetro, `por_cara` en cada lado,
    contando las esquinas una sola vez. `d` es la distancia del borde
    al CENTRO de la barra.

    (y, z) con y hacia el canto h y z hacia el ancho b, que es la
    convencion de fibras de OpenSees.
    """
    a = math.pi * diam ** 2 / 4.0
    y0, z0 = h / 2.0 - d, b / 2.0 - d
    n = max(int(por_cara), 2)
    ys = [-y0 + 2 * y0 * i / (n - 1) for i in range(n)]
    zs = [-z0 + 2 * z0 * i / (n - 1) for i in range(n)]
    puntos = set()
    for y in (ys[0], ys[-1]):
        for z in zs:
            puntos.add((round(y, 6), round(z, 6)))
    for z in (zs[0], zs[-1]):
        for y in ys:
            puntos.add((round(y, 6), round(z, 6)))
    return [(y, z, a) for y, z in sorted(puntos)]


# ============================================================
# LA SECCION EN OPENSEES
# ============================================================
def _armar(sec, nf=FIBRAS_NUCLEO):
    """
    Deja construida en OpenSees la Fiber Section (tag 1) y devuelve
    los tags de material. Modelo 2D: ndm=2, ndf=3.

    Tres materiales, no uno:
      1  hormigon CONFINADO      el nucleo, dentro del estribo
      2  hormigon NO confinado   el recubrimiento, que se pierde antes
      3  acero
    """
    import openseespy.opensees as ops
    conf = sec.confinamiento()
    ops.wipe()
    ops.model('basic', '-ndm', 2, '-ndf', 3)

    if conf:
        ops.uniaxialMaterial('Concrete01', 1, -conf['fcc_kPa'],
                             -conf['eps_cc'], -0.25 * conf['fcc_kPa'],
                             -conf['eps_cu'])
    else:
        ops.uniaxialMaterial('Concrete01', 1, -sec.fpc, -EPS_C0,
                             -0.2 * sec.fpc, -EPS_CU_RECUBRIMIENTO)
    ops.uniaxialMaterial('Concrete01', 2, -sec.fpc, -EPS_C0,
                         0.0, -EPS_CU_RECUBRIMIENTO)
    ops.uniaxialMaterial('Steel01', 3, sec.fy, sec.Es, sec.endurecimiento)

    hc, bc = sec.nucleo()
    yc, zc = hc / 2.0, bc / 2.0
    ops.section('Fiber', 1, '-GJ', 1.0e8)
    # nucleo
    ops.patch('rect', 1, nf, nf, -yc, -zc, yc, zc)
    # recubrimiento: cuatro franjas
    nr = FIBRAS_RECUBRIMIENTO
    ops.patch('rect', 2, nr, nf, -sec.h / 2, -zc, -yc, zc)
    ops.patch('rect', 2, nr, nf, yc, -zc, sec.h / 2, zc)
    ops.patch('rect', 2, nf + 2 * nr, nr, -sec.h / 2, -sec.b / 2,
              sec.h / 2, -zc)
    ops.patch('rect', 2, nf + 2 * nr, nr, -sec.h / 2, zc,
              sec.h / 2, sec.b / 2)
    for y, z, a in sec.barras:
        ops.fiber(y, z, a, 3)
    return conf


def momento_curvatura(sec, P=0.0, nf=FIBRAS_NUCLEO,
                      paso=None, pasos=PASOS_MAXIMOS):
    r"""
    Curva momento-curvatura para una compresion axial P (kN, positiva
    en COMPRESION).

    ----------------------------------------------------------------
    COMO SE IMPONE LA CURVATURA
    ----------------------------------------------------------------
    Un elemento zeroLengthSection entre dos nodos en el mismo punto:
    el "desplazamiento" del GDL 3 es entonces la curvatura y la
    "fuerza" el momento. La axial se aplica primero, en un analisis
    aparte, y se MANTIENE (loadConst) mientras se impone la curvatura
    -- si no, la axial se escalaria junto con ella y la curva no
    seria a P constante.

    ----------------------------------------------------------------
    CRITERIO DE TERMINO
    ----------------------------------------------------------------
    El que manda es el de MATERIAL, no el numerico: se corta cuando
    la fibra mas comprimida del nucleo llega a eps_cu -- la
    deformacion a la que se corta el estribo, calculada con Mander a
    partir del estribo real -- o cuando la barra mas traccionada llega
    a eps_su.

    Las deformaciones no se adivinan: la seccion las devuelve. Con
    `section deformation` se tiene (eps_axial, curvatura) y con eso la
    deformacion de cualquier fibra es

        eps(y) = eps_axial - curvatura * y

    Ademas se corta si el analisis deja de converger, o si el momento
    cae bajo el 80% del maximo. Ese ultimo caso NO es el criterio
    principal: con estribo Ø12a10 y trabas, la seccion es tan ductil
    que llega al limite del acero sin haber perdido momento, y una
    curva cortada "porque se acabaron los pasos" no dice nada.

    El motivo queda en el resultado. No es lo mismo una curva que
    termino por rotura que una que se quedo sin pasos.
    """
    import openseespy.opensees as ops
    if paso is None:
        paso = paso_para(sec)
    conf = _armar(sec, nf)

    ops.node(1, 0.0, 0.0)
    ops.node(2, 0.0, 0.0)
    ops.fix(1, 1, 1, 1)
    ops.fix(2, 0, 1, 0)
    ops.element('zeroLengthSection', 1, 1, 2, 1)

    # --- 1. la axial, y se deja constante ---
    if abs(P) > 1e-9:
        ops.timeSeries('Constant', 1)
        ops.pattern('Plain', 1, 1)
        ops.load(2, -float(P), 0.0, 0.0)     # negativo = compresion
        ops.system('BandGeneral')
        ops.numberer('Plain')
        ops.constraints('Plain')
        ops.test('NormDispIncr', 1.0e-8, 20, 0)
        ops.algorithm('Newton')
        ops.integrator('LoadControl', 0.1)
        ops.analysis('Static')
        if ops.analyze(10) != 0:
            return {'P_kN': P, 'phi': [], 'M': [], 'motivo': 'no converge la axial'}
        ops.loadConst('-time', 0.0)

    # --- 2. la curvatura, en control de desplazamiento ---
    # wipeAnalysis borra el analisis de la axial. Sin esto OpenSees
    # avisa "can't set handler after analysis is created" y se queda
    # con el integrador anterior: la curvatura no se impondria.
    ops.wipeAnalysis()
    ops.timeSeries('Linear', 2)
    ops.pattern('Plain', 2, 2)
    ops.load(2, 0.0, 0.0, 1.0)
    ops.system('BandGeneral')
    ops.numberer('Plain')
    ops.constraints('Plain')
    ops.test('NormDispIncr', 1.0e-8, 20, 0)
    ops.algorithm('Newton')
    ops.integrator('DisplacementControl', 2, 3, paso)
    ops.analysis('Static')

    # Fibras extremas: la del nucleo mas comprimida y la barra mas
    # traccionada. Sus deformaciones son las que deciden el final.
    hc, _bc = sec.nucleo()
    y_nucleo = hc / 2.0
    y_barra = max(abs(y) for y, _z, _a in sec.barras) if sec.barras else 0.0
    eps_cu = conf['eps_cu'] if conf else EPS_CU_RECUBRIMIENTO

    phi, M, motivo = [0.0], [0.0], 'se llego al maximo de pasos'
    eps_c = eps_s = 0.0
    M_aci = phi_aci = None
    for _ in range(pasos):
        if ops.analyze(1) != 0:
            # Newton se atasca justo en el peak del hormigon, donde la
            # rigidez tangente pasa por cero. Antes de darse por
            # vencido se prueba con la matriz inicial y pasos chicos,
            # que es lento pero atraviesa el punto.
            ops.algorithm('ModifiedNewton', '-initial')
            ops.integrator('DisplacementControl', 2, 3, paso / 10.0)
            rescatado = ops.analyze(10) == 0
            ops.algorithm('Newton')
            ops.integrator('DisplacementControl', 2, 3, paso)
            if not rescatado:
                motivo = 'el analisis dejo de converger'
                break
        c = ops.nodeDisp(2, 3)
        m = abs(ops.eleResponse(1, 'section', 'force')[1])
        phi.append(c)
        M.append(m)

        d = ops.eleResponse(1, 'section', 'deformation')
        eps_axial, kappa = float(d[0]), float(d[1])
        eps_c = eps_axial - kappa * y_nucleo      # la mas comprimida
        eps_s = eps_axial + kappa * y_barra       # la mas traccionada
        # El momento cuando el hormigon llega a 0.003: la capacidad
        # NOMINAL, la que se puede contrastar con un calculo a mano.
        if M_aci is None and -eps_c >= EPS_C_ACI:
            M_aci, phi_aci = m, c

        if -eps_c >= eps_cu:
            motivo = ('el nucleo llego a eps_cu = %.5f (se corta el estribo)'
                      % eps_cu)
            break
        if eps_s >= EPS_SU:
            motivo = 'la barra traccionada llego a eps_su = %.3f' % EPS_SU
            break
        if m < 0.8 * max(M):
            motivo = 'el momento cayo bajo el 80% del maximo'
            break

    # Rigidez inicial: la pendiente del primer tramo, antes de que
    # fisure. Se mide sobre los primeros pasos y no sobre el primero
    # solo, que es ruido numerico.
    k = 0.0
    if len(phi) > 4 and phi[4] > 0:
        k = M[4] / phi[4]

    return {
        'P_kN': float(P),
        'phi': phi, 'M': M,
        'M_max': max(M) if M else 0.0,
        'phi_en_M_max': phi[M.index(max(M))] if M else 0.0,
        # Capacidad NOMINAL, con la convencion de ACI: el momento
        # cuando la fibra de hormigon mas comprimida llega a 0.003.
        # Es SIEMPRE menor que M_max, porque despues de ese punto el
        # nucleo confinado sigue tomando carga y el acero endurece.
        'M_aci': M_aci, 'phi_aci': phi_aci,
        'rigidez_inicial_kNm2': k,
        'motivo_termino': motivo,
        'eps_hormigon_final': eps_c,
        'eps_acero_final': eps_s,
        'n_puntos': len(phi),
        'fibras': nf,
        'confinamiento': conf,
    }


def interaccion(sec, niveles=None, nf=FIBRAS_NUCLEO, paso=None):
    r"""
    Curva de interaccion P-M. Cada punto es el momento MAXIMO que la
    seccion alcanza con esa compresion, sacado de su propio M-phi.

    ----------------------------------------------------------------
    LOS DOS EXTREMOS
    ----------------------------------------------------------------
    Traccion pura   P = -As*fy,   M = 0
                    todo el acero fluye en traccion, el hormigon no
                    aporta (Concrete01 no tiene resistencia a
                    traccion)

    Compresion pura P = f'c*(Ag-As) + fy*As,   M = 0
                    sin excentricidad no hay momento; es el tope
                    teorico, mayor que el que admitiria una norma,
                    que lo recorta por excentricidad minima

    Entre medio, cada punto sale de una corrida. Subiendo P el
    momento primero CRECE -- la compresion cierra las fisuras y
    retrasa la fluencia del acero traccionado -- hasta el punto
    BALANCEADO, y despues cae, porque el hormigon se aplasta antes de
    que el acero llegue a fluir. Esa nariz es la respuesta a "por que
    P cambia la capacidad a momento".
    """
    P_traccion = -sec.As * sec.fy
    P_compresion = sec.fpc * (sec.Ag - sec.As) + sec.fy * sec.As

    if niveles is None:
        # Mas densos abajo, que es donde esta la nariz.
        niveles = [P_compresion * f for f in
                   (0.0, 0.05, 0.10, 0.15, 0.20, 0.30, 0.40,
                    0.50, 0.65, 0.80)]

    puntos = [{'P_kN': P_traccion, 'M_kNm': 0.0, 'de': 'traccion pura'}]
    for P in niveles:
        r = momento_curvatura(sec, P=P, nf=nf, paso=paso)
        if not r['M']:
            continue
        puntos.append({
            'P_kN': float(P),
            'M_kNm': r['M_aci'] if r['M_aci'] else r['M_max'],
            'M_max_kNm': r['M_max'],
            'phi_kNm': r['phi_aci'] or r['phi_en_M_max'],
            'de': ('hormigon a 0.003 (nominal)' if r['M_aci']
                   else 'maximo del M-phi'),
            'motivo': r['motivo_termino'],
        })
    puntos.append({'P_kN': P_compresion, 'M_kNm': 0.0,
                   'de': 'compresion pura'})
    return puntos


def sensibilidad_discretizacion(sec, P=0.0, cuantas=(8, 12, 20, 30, 40)):
    """
    Cuanto cambia el momento maximo al refinar las fibras. Es la
    verificacion de que 20 fibras alcanzan: si el resultado todavia se
    mueve, la discretizacion manda sobre la respuesta y el numero no
    es de la seccion, es del mallado.
    """
    salida = []
    for nf in cuantas:
        r = momento_curvatura(sec, P=P, nf=nf)
        salida.append({'fibras': nf, 'M_max': r['M_max'],
                       'rigidez_inicial': r['rigidez_inicial_kNm2']})
    if salida:
        ref = salida[-1]['M_max']
        for s in salida:
            s['error_vs_mas_fino'] = (abs(s['M_max'] - ref) / ref
                                      if ref else 0.0)
    return salida


# ============================================================
def main(argv):
    if not argv:
        print(__doc__)
        return 1
    edificio = argv[0]
    elem = argv[1] if len(argv) > 1 else None
    if elem is None:
        modelo = contrato.cargar_modelo(edificio)
        cols = [e['id'] for e in modelo['elementos'] if 'enfierradura' in e]
        print('Elementos con enfierradura en %s: %s' % (edificio, cols))
        return 0

    modelo = contrato.cargar_modelo(edificio)
    sec = desde_elemento(modelo, elem)

    print('=' * 68)
    print('  CAPACIDAD DE LA SECCION')
    print('=' * 68)
    print(sec.resumen())
    if sec.origen:
        print('  del plano   %s, %s, eje %s'
              % (sec.origen.get('lamina'), sec.origen.get('elevacion'),
                 sec.origen.get('eje')))

    r = momento_curvatura(sec)
    print()
    print('  M-phi a P = 0')
    print('    %d puntos, M maximo = %.1f kN m en phi = %.5f 1/m'
          % (r['n_puntos'], r['M_max'], r['phi_en_M_max']))
    if r['M_aci']:
        print('    nominal (hormigon a 0.003) = %.1f kN m en phi = %.5f 1/m'
              % (r['M_aci'], r['phi_aci']))
    print('    rigidez inicial = %.0f kN m2' % r['rigidez_inicial_kNm2'])
    print('    termino porque %s' % r['motivo_termino'])
    print('    al final: eps hormigon = %.5f, eps acero = %.5f'
          % (r['eps_hormigon_final'], r['eps_acero_final']))

    if '--pm' in argv:
        print()
        print('  Curva P-M')
        print('    %10s %12s %12s   %s'
              % ('P [kN]', 'Mn [kN m]', 'M max', 'de'))
        for p in interaccion(sec):
            print('    %10.1f %12.1f %12.1f   %s'
                  % (p['P_kN'], p['M_kNm'], p.get('M_max_kNm', 0.0), p['de']))

    if '--sensibilidad' in argv:
        print()
        print('  Sensibilidad a la discretizacion (P = 0)')
        for s in sensibilidad_discretizacion(sec):
            print('    %3d fibras  M_max = %8.1f kN m   %.3f %% vs la mas fina'
                  % (s['fibras'], s['M_max'], 100 * s['error_vs_mas_fino']))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
