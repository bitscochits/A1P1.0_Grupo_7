# -*- coding: utf-8 -*-
r"""
================================================================
 comun/calcular.py  -  LA ETAPA DE CALCULO
================================================================
 Lee data/modelo/<edificio>.json, lo resuelve con OpenSees y escribe
 un data/resultados/<edificio>_<caso>.json por cada caso de carga.

 Correr:

   python comun/calcular.py lt2                todos los casos
   python comun/calcular.py lt2 --caso G       solo uno
   python comun/calcular.py ingenieria conjunto    varios de una

 ----------------------------------------------------------------
 ESTE ARCHIVO NO SABE DE QUE EDIFICIO SE TRATA
 ----------------------------------------------------------------
 Y ese es todo el punto. No conoce ejes, ni planos, ni nombres de
 capas: recibe nodos, elementos y cargas, y devuelve numeros. Por eso
 el mismo archivo resuelve el LT2, el edificio de Ingenieria y el
 conjunto de los dos, sin una linea de diferencia.

 El motor es `construir_y_resolver` de comun/servidor_opensees.py --
 la MISMA funcion que usa el servidor cuando Unity pide un reanalisis.
 Una sola implementacion: si alguien la mejora, mejora en los dos
 caminos, y no puede pasar que el visor y la linea de comandos den
 resultados distintos.

 ----------------------------------------------------------------
 QUE QUEDA GUARDADO
 ----------------------------------------------------------------
 Por cada caso, un JSON con:

     desplazamientos     los 6 GDL de cada nodo
     reacciones          los 6 GDL de cada apoyo
     fuerzas_elementos   12 valores por barra, en EJES LOCALES
     equilibrio          carga aplicada vs suma de reacciones
     max_desplazamiento

 Tenerlos en disco significa que consultar "cuanto baja la viga 376"
 deja de re-resolver el modelo entero: se lee el archivo.
================================================================
"""
from __future__ import annotations

import argparse
import os
import sys

_AQUI = os.path.dirname(os.path.abspath(__file__))
if _AQUI not in sys.path:
    sys.path.insert(0, _AQUI)

import contrato                              # noqa: E402
import rutas                                 # noqa: E402
import servidor_opensees as motor            # noqa: E402


# ============================================================
def equilibrio(modelo, caso, res):
    """
    Contrasta lo que se aplico contra lo que reaccionan los apoyos.

    Es la unica verificacion que caza casi cualquier error de armado
    -- salvo justamente los que conservan la carga total, que son los
    que hay que buscar con las verificaciones de cada edificio.
    """
    aplicada = [0.0, 0.0, 0.0]
    for c in caso.get('cargas_nodales', []):
        for i, k in enumerate(('fx', 'fy', 'fz')):
            aplicada[i] += float(c.get(k, 0.0))

    largos = {}
    nodos = {int(n['id']): n for n in modelo['nodos']}
    for e in modelo['elementos']:
        a, b = nodos[int(e['n1'])], nodos[int(e['n2'])]
        largos[int(e['id'])] = sum((b[k] - a[k]) ** 2
                                   for k in ('x', 'y', 'z')) ** 0.5

    # Las distribuidas vienen en ejes LOCALES. Se pasan a globales con
    # los versores que trae el propio elemento; si no vinieran, no se
    # puede afirmar nada y se deja el aporte en cero avisando.
    ejes = {int(e['id']): e for e in modelo['elementos']}
    sin_ejes = 0
    for c in caso.get('cargas_distribuidas', []):
        eid = int(c['elemento'])
        L = largos.get(eid, 0.0)
        e = ejes.get(eid, {})
        base = {'wx': e.get('localX'), 'wy': e.get('localY'), 'wz': e.get('localZ')}
        if not all(base.values()):
            sin_ejes += 1
            continue
        for k in ('wx', 'wy', 'wz'):
            w = float(c.get(k, 0.0))
            if w:
                for i in range(3):
                    aplicada[i] += w * L * base[k][i]

    reaccion = [0.0, 0.0, 0.0]
    for r in res.get('reacciones', []):
        for i, k in enumerate(('fx', 'fy', 'fz')):
            reaccion[i] += float(r.get(k, 0.0))

    return {
        'aplicada_kN': [round(v, 4) for v in aplicada],
        'reaccion_kN': [round(v, 4) for v in reaccion],
        'error_kN': [round(aplicada[i] + reaccion[i], 8) for i in range(3)],
        'elementos_sin_ejes_locales': sin_ejes,
    }


# ============================================================
def calcular(nombre, solo_caso=None, callar=False):
    """Resuelve un edificio y deja un JSON por caso. Devuelve las rutas."""
    modelo = contrato.cargar_modelo(nombre)

    problemas = contrato.validar(modelo)
    if problemas:
        print('  El modelo %r tiene %d problema(s):' % (nombre, len(problemas)))
        for p in problemas[:10]:
            print('    - %s' % p)
        raise SystemExit(1)

    if not callar:
        print('  %s' % contrato.resumen(modelo))

    casos = modelo.get('casos_de_carga', [])
    if solo_caso:
        casos = [c for c in casos if c.get('nombre') == solo_caso]
        if not casos:
            raise SystemExit('  el caso %r no esta en el modelo %r'
                             % (solo_caso, nombre))

    # El motor resuelve TODOS los casos sobre un modelo construido una
    # sola vez, que es lo correcto: reconstruirlo por caso es lento y
    # arriesga que un caso vea un estado sucio del anterior.
    data = dict(modelo)
    data['casos_de_carga'] = casos
    salida = motor.construir_y_resolver(data)

    if not salida.get('ok'):
        print('  AVISO: el analisis no convergio en algun caso.')
    for a in salida.get('avisos', [])[:5]:
        print('  aviso: %s' % a)

    resueltos = salida.get('casos') or [salida]
    rutas_escritas = []
    for caso, res in zip(casos, resueltos):
        nombre_caso = caso.get('nombre', 'unico')
        res = dict(res)
        res['edificio'] = nombre
        res['caso'] = nombre_caso
        res['descripcion'] = caso.get('descripcion', '')
        res['equilibrio'] = equilibrio(modelo, caso, res)
        ruta = contrato.guardar_resultados(nombre, nombre_caso, res)
        rutas_escritas.append(ruta)

        if not callar:
            eq = res['equilibrio']
            # El error se informa RELATIVO: en absoluto no dice nada sin
            # saber cuanto pesa el edificio, y ademas el JSON redondea
            # las cargas a 4 decimales, asi que un error del orden de
            # 1e-4 kN sobre decenas de miles es el redondeo, no el modelo.
            aplicada, reaccion = eq['aplicada_kN'][2], eq['reaccion_kN'][2]
            rel = abs(eq['error_kN'][2]) / max(abs(aplicada), 1e-9)
            print('  caso %-4s  UZ max %9.4f mm'
                  % (nombre_caso, res['max_desplazamiento'] * 1000))
            print('           equilibrio Fz: aplicada %.3f  reaccion %.3f  '
                  'error %.1e kN (%.1e relativo)'
                  % (aplicada, reaccion, abs(eq['error_kN'][2]), rel))
            print('           -> %s' % os.path.relpath(ruta, rutas.RAIZ))

    return rutas_escritas


# ============================================================
def main(argv=None):
    ap = argparse.ArgumentParser(
        description='Resuelve uno o mas modelos y guarda sus resultados.')
    ap.add_argument('edificios', nargs='+',
                    help="nombre del modelo en data/modelo/, sin .json "
                         "(lt2, ingenieria, conjunto)")
    ap.add_argument('--caso', default=None,
                    help='resolver solo este caso de carga (G, Q, EX, EY)')
    args = ap.parse_args(argv)

    for nombre in args.edificios:
        print('=' * 68)
        print(' %s' % nombre.upper())
        print('=' * 68)
        calcular(nombre, args.caso)
        print()
    return 0


if __name__ == '__main__':
    sys.exit(main())
