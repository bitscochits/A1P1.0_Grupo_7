# -*- coding: utf-8 -*-
r"""
================================================================
 semana03/verificar_rc.py  -  LAS FIBRAS CONTRA EL CALCULO A MANO
================================================================
 Calcula los puntos caracteristicos de la seccion con las formulas
 del curso de hormigon armado -- bloque de Whitney, compatibilidad
 de deformaciones -- y los compara contra lo que da la Fiber Section
 de OpenSees.

 Correr:
   python semana03/verificar_rc.py lt2 1        una columna
   python semana03/verificar_rc.py lt2 9        un muro
   python semana03/verificar_rc.py lt2          los dos, resumido

 ----------------------------------------------------------------
 NO SE ESPERA QUE DEN LO MISMO, Y ESA ES LA GRACIA
 ----------------------------------------------------------------
 Las dos cuentas describen la misma seccion con hipotesis distintas,
 y las diferencias son PREDECIBLES. Si aparece una que no se puede
 explicar, hay un error en alguna de las dos.

   COMPRESION PURA. A mano se usa 0.85 f'c: el 0.85 de ACI cubre la
   diferencia entre la probeta y el hormigon de la pieza real. El
   modelo de fibras usa Concrete01, que llega a f'c. La razon entre
   los dos tiene que ser exactamente 0.85 sobre la parte de hormigon.

   FLEXION. A mano el hormigon comprimido se reemplaza por un
   RECTANGULO de 0.85 f'c y altura a = beta1 * c (Whitney). En las
   fibras la distribucion es la parabola de Concrete01, integrada
   fibra por fibra. Las dos dan resultantes parecidas -- para eso se
   calibro el bloque -- pero no iguales.

   TRACCION PURA. Aca si tienen que coincidir exacto: no interviene
   el hormigon, es As * fy y nada mas. Si esta no calza, el error es
   de conteo de barras o de area, no de hipotesis.

   ENDURECIMIENTO DEL ACERO. A mano la barra se topa en fy. En las
   fibras, Steel01 sigue subiendo con 1% de pendiente. Da igual
   mientras las deformaciones sean chicas, pero en flexion pura de un
   MURO no lo son: con c = 0.54 m sobre un canto de 7.95, la barra
   mas traccionada llega a eps = 0.041, donde vale 498 MPa en vez de
   420 -- un 19% mas. En la columna llega a 0.015 y son 446 MPa, un
   6%. Por eso el muro discrepa 11.5% en flexion pura y la columna
   solo 0.7%.

   CONFINAMIENTO. El calculo a mano usa hormigon SIN confinar, con
   f'c. El modelo de fibras confina el nucleo con Mander a partir del
   estribo real, y en esta columna eso da f'cc = 52 MPa. A P = 0 casi
   no se nota -- el hormigon comprimido es poco -- pero en el punto
   balanceado explica la mitad de la diferencia. Por eso el modulo
   corre el modelo de fibras DOS veces, con y sin confinar, y muestra
   el desglose: sin confinamiento la diferencia baja de 14.8% a 7.4%,
   y ese 7.4% es Whitney contra la parabola con axial alto, que es
   una discrepancia conocida del bloque equivalente -- se calibro
   para secciones dominadas por flexion, no por compresion.

 ----------------------------------------------------------------
 CONVENCION
 ----------------------------------------------------------------
 En Seccion, la coordenada y corre a lo largo del canto h, de -h/2 a
 +h/2, y la fibra MAS COMPRIMIDA esta en y = +h/2. La profundidad de
 una barra desde esa cara es entonces  d_i = h/2 - y_i.
================================================================
"""
from __future__ import annotations

import math
import os
import sys

_AQUI = os.path.dirname(os.path.abspath(__file__))
_RAIZ = os.path.dirname(_AQUI)
sys.path.insert(0, os.path.join(_RAIZ, 'comun'))

import capacidad                             # noqa: E402
import contrato                              # noqa: E402

import copy                                  # noqa: E402

EPS_CU = 0.003          # ACI 318 22.2.2.1
FACTOR_ACI = 0.85       # el 0.85 f'c del bloque equivalente


def beta1(fpc_kPa):
    """
    ACI 318-08 10.2.7.3. Vale 0.85 hasta 28 MPa y baja 0.05 por cada
    7 MPa por encima, con piso en 0.65.
    """
    f = fpc_kPa / 1000.0
    if f <= 28.0:
        return 0.85
    return max(0.65, 0.85 - 0.05 * (f - 28.0) / 7.0)


def _capas(sec):
    """
    Las barras agrupadas por profundidad, que es como se calcula a
    mano: (d desde la cara comprimida, area total de esa capa).
    """
    por_d = {}
    for y, _z, a in sec.barras:
        d = round(sec.h / 2.0 - y, 6)
        por_d[d] = por_d.get(d, 0.0) + a
    return sorted(por_d.items())


def compresion_pura(sec):
    """P0 = 0.85 f'c (Ag - As) + fy As.  ACI 318-08 10.3.6."""
    return (FACTOR_ACI * sec.fpc * (sec.Ag - sec.As) + sec.fy * sec.As)


def traccion_pura(sec):
    """Pt = As fy. Sin hormigon: no resiste traccion."""
    return sec.As * sec.fy


def punto(sec, c):
    r"""
    (P, M) para una profundidad de eje neutro c, con el bloque de
    Whitney y compatibilidad de deformaciones.

    P positivo en compresion, M respecto del centro de la seccion.
    """
    b, h = sec.b, sec.h
    a = min(beta1(sec.fpc) * c, h)
    Cc = FACTOR_ACI * sec.fpc * b * a          # kN
    P = Cc
    M = Cc * (h / 2.0 - a / 2.0)

    for d, area in _capas(sec):
        # Deformacion por triangulos semejantes desde la fibra a eps_cu.
        eps = EPS_CU * (c - d) / c if c > 1e-12 else -1.0
        fs = max(-sec.fy, min(sec.fy, sec.Es * eps))
        # Una barra dentro del bloque comprimido ocupa hormigon que ya
        # se conto: se le descuenta 0.85 f'c. Es el clasico
        # (fs - 0.85 f'c) As de los apuntes.
        if d <= a and fs > 0:
            fs -= FACTOR_ACI * sec.fpc
        F = fs * area
        P += F
        M += F * (h / 2.0 - d)
    return P, M


def flexion_pura(sec, tol=1e-6):
    """
    c tal que P = 0, por biseccion. Es el caso de flexion simple del
    curso: la seccion no lleva axial y el equilibrio horizontal fija
    la profundidad del eje neutro.
    """
    lo, hi = 1e-5, sec.h
    P_lo, _ = punto(sec, lo)
    P_hi, _ = punto(sec, hi)
    if P_lo > 0 or P_hi < 0:
        return None
    for _ in range(200):
        med = (lo + hi) / 2.0
        P, _M = punto(sec, med)
        if abs(P) < tol * max(sec.Ag * sec.fpc, 1.0):
            break
        if P < 0:
            lo = med
        else:
            hi = med
    c = (lo + hi) / 2.0
    P, M = punto(sec, c)
    return {'c': c, 'a': beta1(sec.fpc) * c, 'P_kN': P, 'M_kNm': M}


def balanceado(sec):
    """
    El punto balanceado: el hormigon llega a 0.003 justo cuando la
    barra mas traccionada llega a fluir.
    """
    capas = _capas(sec)
    if not capas:
        return None
    d = capas[-1][0]                    # la barra mas profunda
    eps_y = sec.fy / sec.Es
    c = EPS_CU / (EPS_CU + eps_y) * d
    P, M = punto(sec, c)
    return {'c': c, 'd': d, 'eps_y': eps_y,
            'a': beta1(sec.fpc) * c, 'P_kN': P, 'M_kNm': M}


def curva_a_mano(sec, n=24):
    """
    La envolvente entera con el metodo del curso, para poder mirarla
    al lado de la de fibras.
    """
    pts = [{'P_kN': -traccion_pura(sec), 'M_kNm': 0.0, 'de': 'traccion pura'}]
    for i in range(1, n + 1):
        c = sec.h * i / float(n)
        P, M = punto(sec, c)
        pts.append({'P_kN': P, 'M_kNm': M, 'c': c, 'de': 'Whitney'})
    pts.append({'P_kN': compresion_pura(sec), 'M_kNm': 0.0,
                'de': 'compresion pura'})
    return pts


# ============================================================
def comparar(modelo, elemento_id, mostrar=True):
    sec = capacidad.desde_elemento(modelo, elemento_id)
    fib = capacidad.interaccion(sec)

    # --- los tres puntos que se calculan a mano ---
    a_mano = {
        'traccion pura': (-traccion_pura(sec), 0.0),
        'compresion pura': (compresion_pura(sec), 0.0),
    }
    fp = flexion_pura(sec)
    if fp:
        a_mano['flexion pura (P=0)'] = (fp['P_kN'], fp['M_kNm'])
    bal = balanceado(sec)
    if bal:
        a_mano['balanceado'] = (bal['P_kN'], bal['M_kNm'])

    # --- los mismos, sacados de la curva de fibras ---
    de_fibras = {}
    p_trac = min(fib, key=lambda p: p['P_kN'])
    p_comp = max(fib, key=lambda p: p['P_kN'])
    de_fibras['traccion pura'] = (p_trac['P_kN'], p_trac['M_kNm'])
    de_fibras['compresion pura'] = (p_comp['P_kN'], p_comp['M_kNm'])
    p0 = min((p for p in fib if abs(p['P_kN']) < 1e-6),
             key=lambda p: abs(p['P_kN']), default=None)
    if p0:
        de_fibras['flexion pura (P=0)'] = (p0['P_kN'], p0['M_kNm'])
    # El balanceado se compara AL MISMO P, no contra el maximo de la
    # envolvente muestreada. Comparar "el maximo de mi muestreo" contra
    # "el punto exacto" mezcla dos cosas: la diferencia de hipotesis y
    # lo grueso del muestreo. Con diez niveles de axial, el maximo real
    # cae entre dos muestras y la diferencia salia del 14%.
    sin_conf = None
    if bal:
        r = capacidad.momento_curvatura(sec, P=bal['P_kN'])
        M = r['M_aci'] if r.get('M_aci') else r['M_max']
        de_fibras['balanceado'] = (bal['P_kN'], M)

        # La misma seccion pero sin confinar, que es la hipotesis del
        # calculo a mano. Sirve para separar cuanto de la diferencia es
        # el confinamiento y cuanto es Whitney contra la parabola.
        if sec.estribo:
            desnuda = copy.copy(sec)
            desnuda.estribo = {}
            desnuda.trabas_x = desnuda.trabas_y = 0
            r2 = capacidad.momento_curvatura(desnuda, P=bal['P_kN'])
            sin_conf = r2['M_aci'] if r2.get('M_aci') else r2['M_max']
    p_max = max(fib, key=lambda p: p['M_kNm'])
    de_fibras['maximo de la envolvente'] = (p_max['P_kN'], p_max['M_kNm'])

    if mostrar:
        print(sec.resumen())
        print()
        print('    beta1 = %.3f     d (barra mas profunda) = %.4f m'
              % (beta1(sec.fpc), _capas(sec)[-1][0] if _capas(sec) else 0))
        if fp:
            print('    flexion pura: c = %.4f m, a = %.4f m'
                  % (fp['c'], fp['a']))
        if bal:
            print('    balanceado:   c = %.4f m, a = %.4f m, eps_y = %.5f'
                  % (bal['c'], bal['a'], bal['eps_y']))
        print()
        print('    %-20s %14s %14s %14s %14s'
              % ('punto', 'P a mano', 'P fibras', 'M a mano', 'M fibras'))
        for k in ('traccion pura', 'flexion pura (P=0)', 'balanceado',
                  'compresion pura', 'maximo de la envolvente'):
            if k not in a_mano or k not in de_fibras:
                continue
            (Pa, Ma), (Pf, Mf) = a_mano[k], de_fibras[k]
            print('    %-20s %14.1f %14.1f %14.1f %14.1f'
                  % (k, Pa, Pf, Ma, Mf))

        print()
        print('    diferencias, y si se explican:')
        Pa = a_mano['compresion pura'][0]
        Pf = de_fibras['compresion pura'][0]
        # el modelo de fibras usa f'c y el calculo a mano 0.85 f'c
        esperado = (sec.fpc * (sec.Ag - sec.As) + sec.fy * sec.As)
        print('      compresion pura   %.1f contra %.1f kN  (%.1f %%)'
              % (Pa, Pf, 100 * (Pa - Pf) / Pf))
        print('        la de fibras usa f\'c y la de mano 0.85 f\'c; con f\'c')
        print('        el calculo a mano daria %.1f kN, o sea %.2f %% de la'
              % (esperado, 100 * esperado / Pf))
        print('        de fibras. La diferencia es SOLO el 0.85 de ACI.')
        Pa = -traccion_pura(sec)
        Pf = de_fibras['traccion pura'][0]
        print('      traccion pura     %.1f contra %.1f kN  (%.2e relativo)'
              % (Pa, Pf, abs(Pa - Pf) / max(abs(Pf), 1.0)))
        print('        aca NO hay hipotesis distintas: es As*fy. Tiene que')
        print('        coincidir, y coincide.')
        if fp and 'flexion pura (P=0)' in de_fibras:
            Ma = fp['M_kNm']
            Mf = de_fibras['flexion pura (P=0)'][1]
            print('      flexion pura      %.1f contra %.1f kN m  (%.1f %%)'
                  % (Ma, Mf, 100 * (Ma - Mf) / Mf))
            print('        Whitney contra la parabola de Concrete01, y')
            capas = _capas(sec)
            if capas and fp['c'] > 1e-9:
                d = capas[-1][0]
                eps = EPS_CU * (d - fp['c']) / fp['c']
                eps_y = sec.fy / sec.Es
                fs = sec.fy + sec.endurecimiento * sec.Es * max(0.0,
                                                                eps - eps_y)
                print('        sobre todo ENDURECIMIENTO: con c = %.3f m sobre'
                      % fp['c'])
                print('        un canto de %.2f m, la barra mas traccionada'
                      % sec.h)
                print('        llega a eps = %.4f, donde Steel01 da %.0f MPa'
                      % (eps, fs / 1000.0))
                print('        en vez de los %.0f de fy: un %.0f %% mas.'
                      % (sec.fy / 1000.0, 100 * (fs - sec.fy) / sec.fy))
        if 'balanceado' in a_mano and 'balanceado' in de_fibras:
            (Pab, Mab) = a_mano['balanceado']
            (Pfb, Mfb) = de_fibras['balanceado']
            print('      balanceado        M %.1f contra %.1f kN m  (%.1f %%)'
                  % (Mab, Mfb, 100 * (Mab - Mfb) / max(Mfb, 1e-9)))
            print('        los dos evaluados a P = %.0f kN, que es el axial'
                  % Pab)
            print('        balanceado que sale del calculo a mano.')
            if sin_conf:
                print('        la MISMA seccion sin confinar da %.1f kN m '
                      '(%.1f %%):' % (sin_conf,
                                      100 * (Mab - sin_conf) / sin_conf))
                print('        o sea que el confinamiento explica la mitad de')
                print('        la diferencia y el resto es el bloque')
                print('        equivalente con axial alto, donde no fue')
                print('        calibrado.')

    return {'seccion': sec, 'a_mano': a_mano, 'de_fibras': de_fibras,
            'flexion_pura': fp, 'balanceado': bal}


def main(argv):
    if not argv:
        print(__doc__)
        return 1
    edificio = argv[0]
    modelo = contrato.cargar_modelo(edificio)

    if len(argv) > 1:
        elems = [argv[1]]
    else:
        # Una columna y un muro, que es lo que pide el avance.
        col = next((e['id'] for e in modelo['elementos']
                    if e.get('tipo') == 'columna' and 'enfierradura' in e), None)
        mur = next((e['id'] for e in modelo['elementos']
                    if e.get('tipo') == 'muro' and 'enfierradura' in e), None)
        elems = [x for x in (col, mur) if x is not None]

    print('=' * 76)
    print('  VERIFICACION RC: FIBRAS CONTRA CALCULO A MANO')
    print('=' * 76)
    for e in elems:
        print()
        comparar(modelo, e)
        print()
        print('-' * 76)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
