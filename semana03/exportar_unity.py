# -*- coding: utf-8 -*-
r"""
================================================================
 semana03/exportar_unity.py  -  LO QUE EL VISOR DIBUJA DE SEMANA 3
================================================================
 Deja en data/unity/semana03.json -- y una copia en StreamingAssets --
 las cargas, la deformada sismica y la enfierradura, ya resueltas,
 para que VisorSemana03.cs las dibuje sin calcular nada.

 Correr:
   python semana03/exportar_unity.py                 ingenieria
   python semana03/exportar_unity.py lt2 --cs 0.20 --k 2

 Acepta los mismos parametros que lab_semana03.py, y exporta lo que
 el laboratorio corre con ellos: si cambia Cs o el patron, cambian
 las flechas y la deformada. No lee data/resultados/.

 ----------------------------------------------------------------
 LA REGLA DEL REPOSITORIO
 ----------------------------------------------------------------
 OpenSees calcula, Unity muestra. Este archivo no dibuja: arma y
 resuelve los cuatro casos con lab_semana03.armar_casos(), saca la
 seccion de la columna mas cargada con comun/capacidad.py -- la misma
 seccion que usa la Parte D -- y escribe geometria y numeros. Es un
 anexo: no toca modelo_unity.json, asi que el visor, el analizador y
 el editor siguen funcionando sin cambios.

 ----------------------------------------------------------------
 QUE LLEVA
 ----------------------------------------------------------------
 caja        el bounding box del modelo, para ubicar la vista de detalle
 sismo       la fuerza por nivel, con el patron configurado
 cargas      G, Q, EX, EY y la combinacion, como flechas. Las cargas
             distribuidas van reducidas a UNA flecha por barra con la
             resultante w*L: dibujar la carga repartida daria miles de
             objetos y no se leeria mejor
 deformadas  los desplazamientos de EX y EY, para VisorEstructura
 armadura    la jaula de la columna mas cargada -- barras, estribo
             exterior y rombo, en coordenadas de seccion -- y la lista
             de todas las columnas con fierro, para enfierrarlas todas

 Los nombres de las claves son el contrato con VisorSemana03.cs:
 JsonUtility ignora lo que no conoce, pero lo que conoce tiene que
 llamarse igual.
================================================================
"""
from __future__ import annotations

import io
import json
import math
import os
import shutil
import sys

_AQUI = os.path.dirname(os.path.abspath(__file__))
_RAIZ = os.path.dirname(_AQUI)
sys.path.insert(0, os.path.join(_RAIZ, 'comun'))
sys.path.insert(0, _AQUI)

import capacidad                             # noqa: E402
import contrato                              # noqa: E402
import lab_semana03 as lab                   # noqa: E402
import parametros                            # noqa: E402
import rutas                                 # noqa: E402

SALIDA = os.path.join(rutas.UNITY, 'semana03.json')
STREAMING = os.path.join(rutas.STREAMING, 'semana03.json')

# Una carga menor que esta fraccion de la mayor de su caso no se
# exporta: en G hay cientos de barras con cargas chicas que solo
# ensucian la vista.
MINIMA_FRACCION = 0.0


# ============================================================
def bloque_caja(modelo):
    xs = [float(n['x']) for n in modelo['nodos']]
    ys = [float(n['y']) for n in modelo['nodos']]
    zs = [float(n['z']) for n in modelo['nodos']]
    return {'x_min': round(min(xs), 3), 'x_max': round(max(xs), 3),
            'y_min': round(min(ys), 3), 'y_max': round(max(ys), 3),
            'z_min': round(min(zs), 3), 'z_max': round(max(zs), 3)}


def bloque_sismo(arm, nodos, p):
    """La fuerza lateral por nivel, con las coordenadas del maestro
    para que el visor no tenga que cruzar este anexo con el modelo."""
    niveles = []
    for (cota, m), W, f, F in zip(arm['niveles'], arm['pesos_sismicos'],
                                  arm['factores'], arm['fuerzas']):
        n = nodos[m]
        niveles.append({'nodo_maestro': m,
                        'x': round(float(n['x']), 4),
                        'y': round(float(n['y']), 4),
                        'z': round(float(n['z']), 4),
                        'peso_kN': round(W, 3),
                        'fraccion': round(f, 6),
                        'F_kN': round(F, 4)})
    return {'patron': parametros.texto_patron(p),
            'Cs': p['coef_sismico'],
            'fraccion_Q_sismica': p['fraccion_Q_sismica'],
            'corte_basal_kN': round(arm['V'], 4),
            'fuerza_maxima_kN': round(max(arm['fuerzas']), 4),
            'niveles': niveles}


# ============================================================
def _flechas(modelo, caso, factor=1.0):
    """
    Un caso de carga como lista de flechas: punto de aplicacion, vector
    y magnitud. Las nodales van donde estan; las distribuidas se
    reducen a la resultante w*L en el centro de la barra.
    """
    nodos = {int(n['id']): n for n in modelo['nodos']}
    elementos = {int(e['id']): e for e in modelo['elementos']}
    out = []

    for c in caso.get('cargas_nodales', []):
        n = nodos[int(c['nodo'])]
        f = [factor * float(c.get(k, 0.0)) for k in ('fx', 'fy', 'fz')]
        if sum(abs(v) for v in f) > 1e-9:
            out.append(((float(n['x']), float(n['y']), float(n['z'])), f))

    for c in caso.get('cargas_distribuidas', []):
        e = elementos[int(c['elemento'])]
        a, b = nodos[int(e['n1'])], nodos[int(e['n2'])]
        L = lab.largo(e, nodos)
        f = [factor * float(c.get(k, 0.0)) * L for k in ('wx', 'wy', 'wz')]
        if sum(abs(v) for v in f) > 1e-9:
            centro = tuple((float(a[k]) + float(b[k])) / 2.0 for k in ('x', 'y', 'z'))
            out.append((centro, f))
    return out


def _sumar_en_el_mismo_punto(flechas):
    """Dos flechas en el mismo punto son una sola: se suman los vectores."""
    por_punto = {}
    for punto, f in flechas:
        clave = tuple(round(v, 4) for v in punto)
        acum = por_punto.setdefault(clave, [0.0, 0.0, 0.0])
        for i in range(3):
            acum[i] += f[i]
    return [(p, f) for p, f in por_punto.items()
            if sum(abs(v) for v in f) > 1e-9]


def _caso_de_flechas(nombre, descripcion, flechas):
    filas = []
    for (x, y, z), (fx, fy, fz) in flechas:
        filas.append({'x': round(x, 5), 'y': round(y, 5), 'z': round(z, 5),
                      'fx': round(fx, 5), 'fy': round(fy, 5), 'fz': round(fz, 5),
                      'kN': round(math.sqrt(fx * fx + fy * fy + fz * fz), 5)})
    return {'caso': nombre,
            'descripcion': descripcion,
            'maxima_kN': round(max((f['kN'] for f in filas), default=0.0), 4),
            'total_kN': round(sum(f['kN'] for f in filas), 4),
            'flechas': filas}


def bloque_cargas(modelo, arm, lambdas, p):
    """G, Q, EX, EY y la combinacion. La combinacion se arma aca, en
    Python, con los lambda de los parametros: no en C#."""
    que = {'G': 'peso propio y carga muerta',
           'Q': 'carga viva q_Q = %g kN/m2, %s' % (p['q_Q'], parametros.origen_q(p)),
           'EX': 'sismo en X, %s' % parametros.texto_patron(p),
           'EY': 'sismo en Y, %s' % parametros.texto_patron(p)}
    salida = [_caso_de_flechas(n, que[n], _flechas(modelo, arm['casos'][n]))
              for n in lab.CASOS]

    comb = []
    for n in lab.CASOS:
        if abs(lambdas.get(n, 0.0)) > 1e-15:
            comb.extend(_flechas(modelo, arm['casos'][n], lambdas[n]))
    salida.append(_caso_de_flechas('COMBINACION', parametros.como_texto(lambdas),
                                   _sumar_en_el_mismo_punto(comb)))
    return salida


# ============================================================
def bloque_deformadas(resultados):
    """Los desplazamientos de EX y EY, con los campos que espera
    VisorEstructura.AplicarDeformada()."""
    salida = []
    for caso in ('EX', 'EY'):
        ds = [{'id': int(d['id']),
               'ux': round(float(d.get('ux', 0.0)), 8),
               'uy': round(float(d.get('uy', 0.0)), 8),
               'uz': round(float(d.get('uz', 0.0)), 8),
               'rx': round(float(d.get('rx', 0.0)), 8),
               'ry': round(float(d.get('ry', 0.0)), 8),
               'rz': round(float(d.get('rz', 0.0)), 8)}
              for d in resultados[caso].get('desplazamientos', [])]
        maximo = max((math.hypot(d['ux'], d['uy']) for d in ds), default=0.0)
        salida.append({'caso': caso,
                       'max_horizontal_mm': round(maximo * 1000.0, 3),
                       'desplazamientos': ds})
    return salida


# ============================================================
def bloque_armadura(modelo, resultados):
    """
    La jaula de la columna mas cargada bajo G, leida con la MISMA
    funcion que usa la Parte D. Las coordenadas de barras y estribos
    son de seccion (y, z), con el origen en su centro; el visor las
    pone sobre el eje de la columna.
    """
    columnas = [e for e in modelo['elementos']
                if e.get('tipo') == 'columna' and e.get('enfierradura')]
    if not columnas:
        return None
    axial = {int(f['id']): abs(float(f['f'][0]))
             for f in resultados['G'].get('fuerzas_elementos', [])}
    elegida = max(columnas, key=lambda e: axial.get(int(e['id']), 0.0))
    sec = capacidad.desde_elemento(modelo, int(elegida['id']))

    nodos = {int(n['id']): n for n in modelo['nodos']}
    inferior, superior = sorted((nodos[int(elegida['n1'])], nodos[int(elegida['n2'])]),
                                key=lambda n: float(n['z']))

    # El estribo, medido a su eje: es lo que devuelve nucleo().
    hc, bc = sec.nucleo()
    y, z = hc / 2.0, bc / 2.0
    d_barra = 2.0 * math.sqrt(sec.barras[0][2] / math.pi) if sec.barras else 0.0
    fe = elegida['enfierradura']
    fuente = fe.get('fuente') or {}
    origen = (fe.get('longitudinal') or {}).get('origen', '')

    return {
        'columna_id': int(elegida['id']),
        'n1': int(inferior['id']),
        'n2': int(superior['id']),
        'axial_G_kN': round(axial.get(int(elegida['id']), 0.0), 3),
        'b': sec.b,
        'h': sec.h,
        'recubrimiento': sec.rec,
        'diametro_barra': round(d_barra, 5),
        'diametro_estribo': float(sec.estribo.get('diametro_mm', 0.0)) / 1000.0,
        'espaciamiento_estribo': float(sec.estribo.get('separacion_cm', 10.0)) / 100.0,
        'cuantia_pct': round(100.0 * sec.cuantia, 4),
        'as_total_cm2': round(sec.As * 1e4, 3),
        'procedencia': ('lamina %s; %s' % (fuente.get('lamina', '?'), origen)).strip('; '),
        'barras': [{'y': round(by, 5), 'z': round(bz, 5)} for by, bz, _a in sec.barras],
        'estribo_exterior': [{'y': py, 'z': pz} for py, pz in
                             ((y, z), (y, -z), (-y, -z), (-y, z))],
        'estribo_rombo': [{'y': py, 'z': pz} for py, pz in
                          ((y, 0.0), (0.0, -z), (-y, 0.0), (0.0, z))],
        'nodo_inferior': {k: float(inferior[k]) for k in ('x', 'y', 'z')},
        'nodo_superior': {k: float(superior[k]) for k in ('x', 'y', 'z')},
        # Todas las columnas con fierro, por id de nodo: asi el visor
        # puede moverlas con la deformada sin recalcular nada.
        'columnas': [{'id': int(e['id']), 'n1': int(e['n1']), 'n2': int(e['n2']),
                      'axial_G_kN': round(axial.get(int(e['id']), 0.0), 2)}
                     for e in sorted(columnas, key=lambda c: int(c['id']))],
    }


# ============================================================
def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    edificio = 'ingenieria'
    if argv and not argv[0].startswith('-'):
        edificio = argv.pop(0)
    p = parametros.cargar(argv)
    lambdas = parametros.factores(p['combinacion'])

    modelo = contrato.cargar_modelo(edificio)
    nodos = {int(n['id']): n for n in modelo['nodos']}
    arm = lab.armar_casos(modelo, p)
    _datos, resultados = lab.resolver(modelo, arm['casos'])

    anexo = {
        'info': {
            'descripcion': 'Anexo de Semana 3 para el visor: cargas, '
                           'deformada sismica y armadura',
            'edificio': edificio,
            'unidades': 'm, kN',
            'parametros': parametros.describir(p).replace('  ', ' ').split('\n'),
            'nota': 'Calculado por semana03/exportar_unity.py. Unity solo '
                    'dibuja; el calculo vive en Python.',
        },
        'caja': bloque_caja(modelo),
        'sismo': bloque_sismo(arm, nodos, p),
        'cargas': bloque_cargas(modelo, arm, lambdas, p),
        'deformadas': bloque_deformadas(resultados),
        'armadura': bloque_armadura(modelo, resultados),
    }

    rutas.asegurar(SALIDA)
    with io.open(SALIDA, 'w', encoding='utf-8') as f:
        json.dump(anexo, f, indent=1, ensure_ascii=False)
    copiado = os.path.isdir(os.path.dirname(STREAMING))
    if copiado:
        shutil.copy2(SALIDA, STREAMING)

    s, a = anexo['sismo'], anexo['armadura']
    print('=' * 68)
    print('  ANEXO DE SEMANA 3 PARA UNITY   %s' % edificio.upper())
    print('=' * 68)
    print(parametros.describir(p))
    print()
    print('  sismo      %s, corte basal %.2f kN en %d niveles'
          % (s['patron'], s['corte_basal_kN'], len(s['niveles'])))
    for n in s['niveles']:
        print('             z = %+6.2f   %6.2f %%   F = %9.2f kN'
              % (n['z'], 100 * n['fraccion'], n['F_kN']))
    print('  cargas     ' + '   '.join('%s: %d' % (c['caso'], len(c['flechas']))
                                     for c in anexo['cargas']))
    for d in anexo['deformadas']:
        print('  deformada  %s  %d nodos, maximo %.2f mm'
              % (d['caso'], len(d['desplazamientos']), d['max_horizontal_mm']))
    if a:
        print('  armadura   columna %d (%.0f kN en G): %d barras D%.0f, '
              'cuantia %.2f %%; %d columnas con fierro'
              % (a['columna_id'], a['axial_G_kN'], len(a['barras']),
                 a['diametro_barra'] * 1000, a['cuantia_pct'], len(a['columnas'])))
    else:
        print('  armadura   (ninguna columna trae enfierradura)')
    print()
    print('  -> %s' % os.path.relpath(SALIDA, rutas.RAIZ))
    if copiado:
        print('  -> %s' % os.path.relpath(STREAMING, rutas.RAIZ))
    return 0


if __name__ == '__main__':
    sys.exit(main())
