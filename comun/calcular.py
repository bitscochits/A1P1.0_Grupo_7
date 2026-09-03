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
import math
import os
import sys

_AQUI = os.path.dirname(os.path.abspath(__file__))
if _AQUI not in sys.path:
    sys.path.insert(0, _AQUI)

import contrato                              # noqa: E402
import rutas                                 # noqa: E402
import servidor_opensees as motor            # noqa: E402


# ============================================================
def ejes_locales(pi, pj, vecxz):
    """
    Los tres versores locales de una barra, con la MISMA convencion que
    usa OpenSees en geomTransf:

        local_x = (j - i) normalizado
        local_z = componente de vecxz perpendicular a local_x
        local_y = local_z x local_x
    """
    dx = [pj[k] - pi[k] for k in range(3)]
    L = math.sqrt(sum(c * c for c in dx))
    if L < 1e-12:
        return None, 0.0
    ex = [c / L for c in dx]

    proy = sum(vecxz[k] * ex[k] for k in range(3))
    ez = [vecxz[k] - proy * ex[k] for k in range(3)]
    n = math.sqrt(sum(c * c for c in ez))
    if n < 1e-9:
        return None, L
    ez = [c / n for c in ez]

    ey = [ez[1] * ex[2] - ez[2] * ex[1],
          ez[2] * ex[0] - ez[0] * ex[2],
          ez[0] * ex[1] - ez[1] * ex[0]]
    return {'wx': ex, 'wy': ey, 'wz': ez}, L


def equilibrio(modelo, caso, res):
    """
    Contrasta lo que se aplico contra lo que reaccionan los apoyos.

    Es la verificacion que caza casi cualquier error de armado -- salvo
    justamente los que conservan la carga total, que son los que hay que
    buscar con las verificaciones propias de cada edificio.

    ----------------------------------------------------------------
    LAS DISTRIBUIDAS VIENEN EN EJES LOCALES
    ----------------------------------------------------------------
    Para sumarlas con las nodales hay que pasarlas a globales, y para
    eso hacen falta los versores locales de cada barra. Si el JSON los
    trae calculados (localX/localY/localZ) se usan esos, porque son los
    mismos que se le mostraron a Unity. Si no vienen, se reconstruyen
    aca con la misma regla que aplica el solver, incluido su vecxz por
    defecto: (1,0,0) para un elemento vertical, (0,0,1) para el resto.

    Si aun asi queda una carga sin poder convertirse, ESTA FUNCION NO
    EMITE UN VEREDICTO. Devuelve 'confiable': False y dice cuantas
    quedaron fuera. Un chequeo de equilibrio que ignora en silencio
    parte de la carga es peor que no tenerlo: da un error enorme y
    parece que el modelo esta roto, o da cero y parece que esta sano.
    """
    aplicada = [0.0, 0.0, 0.0]
    for c in caso.get('cargas_nodales', []):
        for i, k in enumerate(('fx', 'fy', 'fz')):
            aplicada[i] += float(c.get(k, 0.0))

    nodos = {int(n['id']): n for n in modelo['nodos']}
    elementos = {int(e['id']): e for e in modelo['elementos']}

    sin_convertir = 0
    for c in caso.get('cargas_distribuidas', []):
        eid = int(c['elemento'])
        e = elementos.get(eid)
        if e is None:
            sin_convertir += 1
            continue

        a, b = nodos[int(e['n1'])], nodos[int(e['n2'])]
        pi = (a['x'], a['y'], a['z'])
        pj = (b['x'], b['y'], b['z'])

        if e.get('localX') and e.get('localY') and e.get('localZ'):
            base = {'wx': e['localX'], 'wy': e['localY'], 'wz': e['localZ']}
            L = math.sqrt(sum((pj[k] - pi[k]) ** 2 for k in range(3)))
        else:
            # Mismo criterio que construir_modelo() del servidor.
            vertical = (abs(pj[0] - pi[0]) < 1e-6 and abs(pj[1] - pi[1]) < 1e-6)
            vecxz = e.get('vecxz') or ((1.0, 0.0, 0.0) if vertical
                                       else (0.0, 0.0, 1.0))
            base, L = ejes_locales(pi, pj, [float(v) for v in vecxz])

        if base is None:
            sin_convertir += 1
            continue

        for k in ('wx', 'wy', 'wz'):
            w = float(c.get(k, 0.0))
            if w:
                for i in range(3):
                    aplicada[i] += w * L * base[k][i]

    # ------------------------------------------------------------
    # NO TODA FILA DE 'reacciones' ES UNA REACCION DE APOYO
    # ------------------------------------------------------------
    # `nodeReaction` en un nodo atado por un diafragma devuelve tambien
    # la fuerza de esa RESTRICCION, que es INTERNA: se cancela de a pares
    # dentro del piso y no tiene por que aparecer en el equilibrio
    # global. Sumarla sin pensar da desastres -- en el caso sismico el
    # corte se aplica en el nodo maestro y reaparece ahi con el signo
    # cambiado, asi que el total sale al doble o al triple.
    #
    # Y no se puede simplemente descartar los nodos del diafragma: los
    # arranques de muro escalonados SON apoyos verticales de verdad
    # (tienen uz restringido contra el terreno) y ademas participan del
    # diafragma en horizontal. Descartarlos entero dejaria fuera 1504 kN
    # de peso propio en el edificio de Ingenieria.
    #
    # La separacion correcta es POR GRADO DE LIBERTAD:
    #
    #   - un diafragma horizontal (perpendicular = 3) ata ux, uy y rz.
    #     En Fx y Fy, entonces, solo valen los nodos que NO estan en
    #     ningun diafragma: los apoyos de la base.
    #   - uz queda libre del diafragma, asi que en Fz vale cualquier nodo
    #     restringido -- salvo el MAESTRO, cuyo uz lo restringio el
    #     solver por necesidad numerica y no es un apoyo real.
    maestros = {int(d['nodo_maestro']) for d in modelo.get('diafragmas', [])}
    en_diafragma = set(maestros)
    atadas = set()          # indices de traslacion que ata algun diafragma
    for d in modelo.get('diafragmas', []):
        en_diafragma |= {int(s) for s in d.get('nodos', [])}
        p = int(d.get('perpendicular', 3))
        atadas |= {0: {1, 2}, 1: {1, 2}, 2: {0, 2}, 3: {0, 1}}.get(p, {0, 1})

    reaccion = [0.0, 0.0, 0.0]
    for r in res.get('reacciones', []):
        nid = int(r['id'])
        if nid in maestros:
            continue
        for i, k in enumerate(('fx', 'fy', 'fz')):
            if i in atadas and nid in en_diafragma:
                continue
            reaccion[i] += float(r.get(k, 0.0))

    return {
        'aplicada_kN': [round(v, 4) for v in aplicada],
        'reaccion_kN': [round(v, 4) for v in reaccion],
        'error_kN': [round(aplicada[i] + reaccion[i], 8) for i in range(3)],
        'cargas_sin_convertir': sin_convertir,
        'nodos_en_diafragma': len(en_diafragma),
        'confiable': sin_convertir == 0,
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
            print('  caso %-4s  UZ max %9.4f mm'
                  % (nombre_caso, res['max_desplazamiento'] * 1000))
            if not eq['confiable']:
                print('           equilibrio: NO SE PUEDE AFIRMAR NADA -- %d '
                      'carga(s) distribuida(s) no se pudieron pasar a ejes '
                      'globales' % eq['cargas_sin_convertir'])
            else:
                # El error se informa tambien RELATIVO: en absoluto no dice
                # nada sin saber cuanto pesa el edificio, y ademas el JSON
                # redondea las cargas, asi que un error de 1e-4 kN sobre
                # decenas de miles es el redondeo, no el modelo.
                #
                # La escala es la MAYOR de las tres componentes, no la de
                # cada una: en un caso sismico horizontal la carga vertical
                # es cero por construccion, y dividir por ella convertiria
                # el redondeo en un "error relativo del 100%".
                escala = max(max(abs(eq['aplicada_kN'][i]),
                                 abs(eq['reaccion_kN'][i])) for i in range(3))
                escala = max(escala, 1e-9)
                peor = max(range(3), key=lambda i: abs(eq['error_kN'][i]))
                comp = 'FxFyFz'[peor * 2:peor * 2 + 2]
                print('           equilibrio %s: aplicada %.3f  reaccion %.3f'
                      % (comp, eq['aplicada_kN'][peor], eq['reaccion_kN'][peor]))
                print('           peor error %.1e kN sobre %.1f kN  '
                      '(%.1e relativo)'
                      % (abs(eq['error_kN'][peor]), escala,
                         abs(eq['error_kN'][peor]) / escala))
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
