# -*- coding: utf-8 -*-
r"""
================================================================
 semana03/demanda_capacidad.py  -  EL PUNTO SOBRE LA CURVA
================================================================
 Toma cualquier columna o muro del edificio, saca su (P, M) de los
 resultados ya calculados y lo pone sobre SU curva de interaccion.

 Correr:
   python semana03/demanda_capacidad.py lt2 --lista
   python semana03/demanda_capacidad.py lt2 1               columna
   python semana03/demanda_capacidad.py lt2 9               muro
   python semana03/demanda_capacidad.py lt2 1 --comb 1.2 1.6 1.0 0.3
   python semana03/demanda_capacidad.py lt2 1 --grafico
   python semana03/demanda_capacidad.py lt2 --todas

 ----------------------------------------------------------------
 LA DEMANDA NO SE VUELVE A CALCULAR
 ----------------------------------------------------------------
 Sale de data/resultados/<edificio>_<caso>.json, que ya estan en
 disco. Cambiar los factores de una combinacion NO obliga a resolver
 de nuevo: el modelo es lineal elastico, asi que las fuerzas se
 combinan algebraicamente. Lo que si obliga a reanalizar es cambiar
 una seccion, un apoyo, E o la geometria.

 La CAPACIDAD si se calcula cada vez, porque es no lineal y no se
 puede superponer. Cuesta menos de un segundo por columna.

 ----------------------------------------------------------------
 QUE ES P Y QUE ES M EN UNA BARRA
 ----------------------------------------------------------------
 De eleResponse(tag, 'localForce') salen doce numeros, seis por
 extremo:

     [N, Vy, Vz, T, My, Mz]  en el nudo i, y lo mismo en el j

 En una columna el eje local x es vertical, asi que N es la carga
 axial: POSITIVA EN COMPRESION en el extremo i. Y hay DOS momentos,
 My y Mz, uno por cada direccion de flexion. La columna no se
 flecta solo en un plano.

 En una COLUMNA cuadrada con armadura perimetral se compara con el
 momento RESULTANTE, sqrt(My^2 + Mz^2): su capacidad es practicamente
 la misma en cualquier direccion.

 En un MURO no. Un M 0.25x7.95 tiene mil veces mas inercia en un eje
 que en el otro, asi que se toma solo el momento EN SU PLANO -- que
 es Mz -- y el de fuera de plano se informa aparte. Ver demanda().
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
import rutas                                 # noqa: E402

CASOS = ('G', 'Q', 'EX', 'EY')


def fuerzas_por_caso(edificio, elemento_id, casos=CASOS):
    """El vector de fuerza local del elemento, en cada caso."""
    salida = {}
    for c in casos:
        ruta = rutas.resultados(edificio, c)
        if not os.path.isfile(ruta):
            continue
        r = contrato.cargar_resultados(edificio, c)
        for f in r.get('fuerzas_elementos', []):
            if int(f['id']) == int(elemento_id):
                salida[c] = [float(v) for v in f['f']]
                break
    return salida


def combinar(por_caso, lambdas):
    """
    Suma algebraica de las fuerzas de varios casos. Es valida porque
    el modelo es lineal: K u = F, y por lo tanto la respuesta a una
    suma de cargas es la suma de las respuestas.
    """
    n = max((len(v) for v in por_caso.values()), default=12)
    out = [0.0] * n
    for caso, factor in lambdas.items():
        f = por_caso.get(caso)
        if not f:
            continue
        for i, v in enumerate(f):
            out[i] += factor * v
    return out


def demanda(f, tipo='columna'):
    r"""
    (P, M) de un vector de fuerza local. P positivo en COMPRESION.

    Se mira en los DOS extremos y gana el que tenga mayor momento: el
    maximo de una columna no siempre esta arriba.

    ----------------------------------------------------------------
    UNA COLUMNA Y UN MURO NO SE MIDEN IGUAL
    ----------------------------------------------------------------
    COLUMNA: seccion cuadrada con armadura perimetral, capacidad
    practicamente igual en cualquier direccion. Se compara con el
    momento RESULTANTE, sqrt(My^2 + Mz^2).

    MURO: la capacidad es enorme en su plano y ridicula fuera de el
    -- un M 0.25x7.95 tiene mil veces mas inercia en un eje que en el
    otro. Componer los dos momentos en uno resultante y compararlo
    contra la curva del plano fuerte diria que el muro aguanta fuera
    de su plano lo mismo que dentro, que es falso. Se toma solo el
    momento EN EL PLANO, que es Mz, y el fuera de plano se informa
    aparte.

    Que Mz es el del plano se comprobo: el muro 9 corre en Y, y bajo
    sismo EY su Mz sube a 9249 kN m mientras My se queda en 23.
    """
    if not f or len(f) < 12:
        return None
    extremos = [
        {'P_kN': f[0], 'My': f[4], 'Mz': f[5], 'extremo': 'i (inferior)'},
        {'P_kN': -f[6], 'My': f[10], 'Mz': f[11], 'extremo': 'j (superior)'},
    ]
    for d in extremos:
        if tipo == 'muro':
            d['M_kNm'] = abs(d['Mz'])
            d['M_fuera_de_plano_kNm'] = abs(d['My'])
        else:
            d['M_kNm'] = math.hypot(d['My'], d['Mz'])
            d['M_fuera_de_plano_kNm'] = None
    return max(extremos, key=lambda d: d['M_kNm'])


def capacidad_en(P, curva):
    """
    Momento que la curva admite para esa compresion, interpolando
    entre los dos puntos que la rodean. Fuera del rango de la curva
    devuelve 0: una compresion mayor que la de compresion pura no la
    resiste nadie.
    """
    pts = sorted(((p['P_kN'], p['M_kNm']) for p in curva),
                 key=lambda t: t[0])
    if not pts or P <= pts[0][0] or P >= pts[-1][0]:
        return 0.0
    for (p1, m1), (p2, m2) in zip(pts, pts[1:]):
        if p1 <= P <= p2:
            if abs(p2 - p1) < 1e-9:
                return max(m1, m2)
            t = (P - p1) / (p2 - p1)
            return m1 + t * (m2 - m1)
    return 0.0


def revisar(edificio, elemento_id, lambdas=None, curva=None, modelo=None):
    """Demanda, capacidad y utilizacion de una columna."""
    modelo = modelo or contrato.cargar_modelo(edificio)
    sec = capacidad.desde_elemento(modelo, elemento_id)
    curva = curva if curva is not None else capacidad.interaccion(sec)

    tipo = next((e.get('tipo') for e in modelo['elementos']
                 if int(e['id']) == int(elemento_id)), 'columna')
    por_caso = fuerzas_por_caso(edificio, elemento_id)
    puntos = {}
    for c, f in por_caso.items():
        puntos[c] = demanda(f, tipo)
    if lambdas:
        puntos['COMB'] = demanda(combinar(por_caso, lambdas), tipo)

    for nombre, d in puntos.items():
        if not d:
            continue
        Mc = capacidad_en(d['P_kN'], curva)
        d['M_capacidad_kNm'] = Mc
        d['utilizacion'] = (d['M_kNm'] / Mc) if Mc > 1e-9 else float('inf')
        d['pasa'] = d['utilizacion'] <= 1.0
    return {'seccion': sec, 'curva': curva, 'puntos': puntos}


def grafico(res, elemento_id, destino):
    """Dibuja la curva y los puntos de demanda."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    pts = sorted(((p['P_kN'], p['M_kNm']) for p in res['curva']),
                 key=lambda t: t[0])
    P = [p for p, _m in pts]
    M = [m for _p, m in pts]

    fig, ax = plt.subplots(figsize=(7.5, 6))
    # Las dos ramas: la seccion es simetrica, el momento puede ir en
    # cualquier sentido.
    ax.plot(M, P, '-', color='#1f4e79', lw=2, label='capacidad nominal')
    ax.plot([-m for m in M], P, '-', color='#1f4e79', lw=2)
    ax.fill_betweenx(P, [-m for m in M], M, color='#1f4e79', alpha=0.07)

    colores = {'G': '#2e7d32', 'Q': '#f9a825', 'EX': '#c62828',
               'EY': '#6a1b9a', 'COMB': '#000000'}
    for nombre, d in res['puntos'].items():
        if not d:
            continue
        ax.plot(d['M_kNm'], d['P_kN'], 'o', ms=9,
                color=colores.get(nombre, '#555'),
                markeredgecolor='white', zorder=5,
                label='%s   u = %.2f' % (nombre, d['utilizacion']))

    ax.axhline(0, color='#999', lw=0.8)
    ax.axvline(0, color='#999', lw=0.8)
    ax.set_xlabel('Momento M [kN m]')
    ax.set_ylabel('Compresion P [kN]')
    ax.set_title('%s\ndemanda contra capacidad' % res['seccion'].nombre)
    ax.grid(alpha=0.25)
    ax.legend(loc='upper right', fontsize=9)
    fig.tight_layout()
    fig.savefig(destino, dpi=150)
    plt.close(fig)
    return destino


# ============================================================
def _lista(edificio):
    modelo = contrato.cargar_modelo(edificio)
    nodos = {int(n['id']): n for n in modelo['nodos']}
    filas = []
    for e in modelo['elementos']:
        fe = e.get('enfierradura')
        if not fe:
            continue
        n1 = nodos[int(e['n1'])]
        if fe.get('tipo') == 'muro':
            cuantas = len(fe.get('barras_de_borde') or [])
        else:
            cuantas = fe['longitudinal']['cantidad']
        filas.append((int(e['id']), float(n1['x']), float(n1['y']),
                      float(n1['z']), e['seccion'], cuantas,
                      (fe.get('fuente') or {}).get('eje')))
    print('%d elementos con enfierradura en %s' % (len(filas), edificio))
    print('  %5s %9s %9s %8s  %-14s %7s  %s'
          % ('elem', 'x', 'y', 'z', 'seccion', 'barras', 'eje'))
    for f in sorted(filas, key=lambda t: (t[1], t[2], t[3])):
        print('  %5d %9.2f %9.2f %+8.2f  %-14s %7d  %s' % f)
    return 0


def _todas(edificio, lambdas):
    modelo = contrato.cargar_modelo(edificio)
    ids = [int(e['id']) for e in modelo['elementos'] if 'enfierradura' in e]
    # Una curva por FAMILIA de enfierradura, no una por elemento: las
    # 40 columnas del LT2 son solo dos secciones distintas, y calcular
    # cuarenta veces la misma curva es tirar el tiempo.
    curvas = {}
    print('  %5s %10s %10s %10s %7s  %s'
          % ('elem', 'P [kN]', 'M [kN m]', 'Mn [kN m]', 'u', ''))
    peor = None
    for eid in ids:
        sec = capacidad.desde_elemento(modelo, eid)
        clave = (len(sec.barras), sec.estribo.get('texto'))
        if clave not in curvas:
            curvas[clave] = capacidad.interaccion(sec)
        res = revisar(edificio, eid, lambdas, curva=curvas[clave],
                      modelo=modelo)
        d = res['puntos'].get('COMB') or res['puntos'].get('G')
        if not d:
            continue
        print('  %5d %10.1f %10.1f %10.1f %7.3f  %s'
              % (eid, d['P_kN'], d['M_kNm'], d['M_capacidad_kNm'],
                 d['utilizacion'], '' if d['pasa'] else '<-- NO PASA'))
        if peor is None or d['utilizacion'] > peor[1]['utilizacion']:
            peor = (eid, d)
    print()
    print('  %d curvas distintas para %d columnas' % (len(curvas), len(ids)))
    if peor:
        print('  la mas exigida es la %d, con u = %.3f'
              % (peor[0], peor[1]['utilizacion']))
    return 0


def main(argv):
    if not argv:
        print(__doc__)
        return 1
    edificio = argv[0]
    resto = argv[1:]

    lambdas = None
    if '--comb' in resto:
        i = resto.index('--comb')
        try:
            f = [float(x) for x in resto[i + 1:i + 5]]
        except (ValueError, IndexError):
            raise SystemExit('--comb necesita cuatro numeros: G Q EX EY')
        lambdas = dict(zip(CASOS, f))
        resto = resto[:i] + resto[i + 5:]

    if '--lista' in resto:
        return _lista(edificio)
    if '--todas' in resto:
        return _todas(edificio, lambdas or {'G': 1.0, 'Q': 1.0,
                                            'EX': 0.0, 'EY': 0.0})

    if not resto:
        raise SystemExit('falta el numero de elemento (o --lista / --todas)')
    elem = resto[0]

    res = revisar(edificio, elem, lambdas)
    sec = res['seccion']

    print('=' * 72)
    print('  DEMANDA CONTRA CAPACIDAD   %s, elemento %s' % (edificio, elem))
    print('=' * 72)
    print(sec.resumen())
    if sec.origen:
        print('  del plano   %s, %s' % (sec.origen.get('lamina'),
                                        sec.origen.get('elevacion')))
    print()
    if lambdas:
        print('  combinacion  ' + ' + '.join(
            '%.2f %s' % (v, k) for k, v in lambdas.items() if v))
        print()
    print('  %-6s %10s %10s %10s %10s %8s  %s'
          % ('caso', 'P [kN]', 'My', 'Mz', 'M', 'Mn', 'utilizacion'))
    for nombre in list(CASOS) + ['COMB']:
        d = res['puntos'].get(nombre)
        if not d:
            continue
        print('  %-6s %10.1f %10.1f %10.1f %10.1f %8.1f  %6.3f  %s'
              % (nombre, d['P_kN'], d['My'], d['Mz'], d['M_kNm'],
                 d['M_capacidad_kNm'], d['utilizacion'],
                 'ok' if d['pasa'] else 'NO PASA'))

    if '--grafico' in resto:
        destino = os.path.join(_AQUI, 'resultados',
                               'pm_%s_%s.png' % (edificio, elem))
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        grafico(res, elem, destino)
        print()
        print('  -> %s' % os.path.relpath(destino, rutas.RAIZ))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
