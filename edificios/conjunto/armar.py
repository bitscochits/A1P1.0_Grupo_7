# -*- coding: utf-8 -*-
r"""
================================================================
 edificios/conjunto/armar.py  -  LOS DOS CUERPOS EN UN MODELO
================================================================
 Junta el edificio de Ingenieria (planos 2017_67) y el LT2 (planos
 2024_22) en un solo modelo, aplicando el calce declarado en
 calce.json.

 Correr:  python edificios/conjunto/armar.py
 Luego:   python comun/calcular.py conjunto

 ----------------------------------------------------------------
 ESTE ARCHIVO NO SABE DE PLANOS
 ----------------------------------------------------------------
 Lee dos data/modelo/<edificio>.json y escribe uno. No abre un DXF,
 no conoce una capa, no sabe que eje es cual. Ese es justamente el
 punto del formato neutro: a ese nivel un edificio ya es una lista de
 nodos y elementos en coordenadas absolutas, y unirlos es geometria y
 renumeracion, no fusionar dos programas.

 Si el modelo de un edificio todavia no esta armado, se arma al vuelo
 llamando a su exportador -- sin escribir nada en su carpeta.

 ----------------------------------------------------------------
 LA JUNTA DE DILATACION
 ----------------------------------------------------------------
 Por defecto NINGUN elemento cruza la junta, y es lo correcto: una
 junta existe para que los dos cuerpos se muevan independientes. El
 conjunto igual sirve para

   - ver el edificio entero en el visor,
   - comprobar que los dos cuerpos no se solapen ni dejen un hueco,
   - sumar todo el peso que baja al terreno,
   - y mas adelante, comprobar que la suma de derivas de los dos
     cuerpos no supere el ancho de la junta (golpeteo).

 ----------------------------------------------------------------
 RENUMERAR NO ES SOLO CAMBIAR LA LISTA DE NODOS
 ----------------------------------------------------------------
 Un tag aparece en siete lugares distintos, y olvidarse de uno no
 hace fallar a OpenSees: si queda una carga apuntando a un elemento
 que no existe, avisa por consola y LA DESCARTA. El analisis corre
 con menos peso del que uno cree y el equilibrio cierra igual, porque
 lo descartado nunca entro. Por eso este archivo remapea todo de una
 sola vez (`_remapear`) y llama a contrato.validar() antes de guardar.
================================================================
"""
from __future__ import annotations

import io
import json
import math
import os
import sys

_AQUI = os.path.dirname(os.path.abspath(__file__))
_RAIZ = os.path.dirname(os.path.dirname(_AQUI))
sys.path.insert(0, os.path.join(_RAIZ, 'comun'))

import contrato                              # noqa: E402
import rutas                                 # noqa: E402

NOMBRE = 'conjunto'
CALCE = os.path.join(_AQUI, 'calce.json')

# Cuanto se le suma a los tags de cada edificio para que no choquen.
# Se deja redondo a proposito: mirando un tag del conjunto se sabe de
# que cuerpo viene (1xxx = Ingenieria, 2xxx = LT2).
PASO_DE_TAG = 100000


# ============================================================
# CARGAR CADA EDIFICIO
# ============================================================
def modelo_de(nombre: str) -> dict:
    """
    El modelo de un edificio. Si data/modelo/<nombre>.json todavia no
    existe, se arma al vuelo con el exportador de ese edificio -- sin
    escribir nada en su carpeta.
    """
    ruta = rutas.modelo(nombre)
    if os.path.isfile(ruta):
        print('  %-11s  %s' % (nombre, os.path.relpath(ruta, rutas.RAIZ)))
        return contrato.cargar_modelo(nombre)

    print('  %-11s  no esta armado todavia: lo construyo al vuelo' % nombre)
    carpeta = rutas.edificio(nombre)
    sys.path.insert(0, carpeta)

    # Cada edificio expone su modelo completo de una forma; se prueban
    # las dos que existen hoy.
    for modulo, funcion in (('exportar_unity', 'construir'),
                            ('export_unity', 'construir_json')):
        if not os.path.isfile(os.path.join(carpeta, modulo + '.py')):
            continue
        mod = __import__(modulo)
        completo = getattr(mod, funcion)()
        estructura, _vista = contrato.separar(completo)
        return estructura

    raise SystemExit(
        '  No se como armar %r. Necesita un data/modelo/%s.json, o un\n'
        '  exportador en %s que devuelva el modelo completo.'
        % (nombre, nombre, os.path.relpath(carpeta, rutas.RAIZ)))


# ============================================================
# MOVER Y RENUMERAR
# ============================================================
def _mover(x, y, dx, dy, cos_g, sin_g):
    """Gira alrededor del origen y despues traslada."""
    return (x * cos_g - y * sin_g + dx,
            x * sin_g + y * cos_g + dy)


def _remapear(modelo: dict, nombre: str, calce: dict, base: int) -> dict:
    """
    Devuelve una copia del modelo con el calce aplicado y los tags
    corridos en `base`. Toca TODOS los lugares donde vive un tag.
    """
    dx = float(calce.get('dx', 0.0))
    dy = float(calce.get('dy', 0.0))
    g = math.radians(float(calce.get('giro_grados', 0.0)))
    cos_g, sin_g = math.cos(g), math.sin(g)

    n_ = lambda i: int(i) + base          # noqa: E731  nodo
    e_ = lambda i: int(i) + base          # noqa: E731  elemento
    s_ = lambda s: '%s:%s' % (nombre, s)  # noqa: E731  seccion

    out = {'info': dict(modelo.get('info', {}))}
    out['info']['edificio'] = nombre
    out['info']['calce'] = {'dx': dx, 'dy': dy,
                            'giro_grados': calce.get('giro_grados', 0.0)}
    if 'material' in modelo:
        out['material'] = modelo['material']

    # --- secciones: el nombre lleva prefijo, porque los dos edificios
    #     tienen secciones distintas que se llaman igual (C50x50...) ---
    out['secciones'] = []
    for s in modelo.get('secciones', []):
        s = dict(s)
        s['nombre'] = s_(s['nombre'])
        out['secciones'].append(s)

    # --- nodos ---
    out['nodos'] = []
    for n in modelo.get('nodos', []):
        n = dict(n)
        n['id'] = n_(n['id'])
        n['x'], n['y'] = _mover(n['x'], n['y'], dx, dy, cos_g, sin_g)
        n['x'], n['y'] = round(n['x'], 4), round(n['y'], 4)
        out['nodos'].append(n)

    # --- elementos ---
    out['elementos'] = []
    for e in modelo.get('elementos', []):
        e = dict(e)
        e['id'] = e_(e['id'])
        e['n1'], e['n2'] = n_(e['n1']), n_(e['n2'])
        e['seccion'] = s_(e['seccion'])
        # Los versores locales y vecxz giran con el edificio. Con giro 0
        # quedan igual, pero dejarlo escrito evita que un giro futuro los
        # deje apuntando al lado equivocado en silencio.
        for k in ('vecxz', 'localX', 'localY', 'localZ', 'dir_largo'):
            v = e.get(k)
            if v and len(v) >= 2:
                a, b = _mover(v[0], v[1], 0.0, 0.0, cos_g, sin_g)
                e[k] = [round(a, 6), round(b, 6)] + list(v[2:])
        out['elementos'].append(e)

    # --- diafragmas y brazos rigidos ---
    out['diafragmas'] = [{**d,
                          'nodo_maestro': n_(d['nodo_maestro']),
                          'nodos': [n_(s) for s in d.get('nodos', [])]}
                         for d in modelo.get('diafragmas', [])]
    out['brazos_rigidos'] = [{**b,
                              'maestro': n_(b['maestro']),
                              'esclavo': n_(b['esclavo'])}
                             for b in modelo.get('brazos_rigidos', [])]

    # --- casos de carga ---
    out['casos_de_carga'] = []
    for c in modelo.get('casos_de_carga', []):
        out['casos_de_carga'].append({
            'nombre': c.get('nombre', '?'),
            'descripcion': c.get('descripcion', ''),
            'cargas_nodales': [{**x, 'nodo': n_(x['nodo'])}
                               for x in c.get('cargas_nodales', [])],
            'cargas_distribuidas': [{**x, 'elemento': e_(x['elemento'])}
                                    for x in c.get('cargas_distribuidas', [])],
        })
    return out


# ============================================================
# UNIR
# ============================================================
def unir(partes: list) -> dict:
    """
    Concatena los modelos ya movidos y renumerados. Los casos de carga
    se unen POR NOMBRE: la G de un cuerpo y la G del otro son el mismo
    caso, y tienen que resolverse juntas.

    Un caso que solo existe en un cuerpo (EX y EY hoy solo estan en el
    edificio de Ingenieria) queda igual, con el otro cuerpo descargado.
    Eso es correcto y no es un error, pero conviene saberlo al leer los
    resultados.
    """
    conjunto = {
        'info': {
            'descripcion': 'Edificio de Ingenieria UAndes: los dos cuerpos',
            'unidades': 'm, kN, kPa',
            'cuerpos': [p['info'].get('edificio') for p in partes],
        },
        'material': partes[0].get('material'),
        'secciones': [], 'nodos': [], 'elementos': [],
        'diafragmas': [], 'brazos_rigidos': [], 'casos_de_carga': [],
    }

    casos = {}
    orden = []
    for p in partes:
        for k in ('secciones', 'nodos', 'elementos', 'diafragmas',
                  'brazos_rigidos'):
            conjunto[k].extend(p.get(k, []))
        for c in p.get('casos_de_carga', []):
            n = c['nombre']
            if n not in casos:
                casos[n] = {'nombre': n, 'descripcion': c.get('descripcion', ''),
                            'cargas_nodales': [], 'cargas_distribuidas': [],
                            '_cuerpos': []}
                orden.append(n)
            casos[n]['cargas_nodales'].extend(c.get('cargas_nodales', []))
            casos[n]['cargas_distribuidas'].extend(c.get('cargas_distribuidas', []))
            casos[n]['_cuerpos'].append(p['info'].get('edificio'))

    for n in orden:
        c = casos[n]
        cuerpos = c.pop('_cuerpos')
        if len(cuerpos) < len(partes):
            c['descripcion'] += ('   [OJO: este caso solo esta definido en %s; '
                                 'el resto del edificio va descargado]'
                                 % ', '.join(cuerpos))
        conjunto['casos_de_carga'].append(c)

    return conjunto


def revisar_la_junta(conjunto, partes, junta):
    """
    Los dos cuerpos no se pueden solapar. Devuelve una lista de avisos.

    No es un chequeo estructural sino GEOMETRICO, y es el unico que hoy
    puede delatar que el calce esta mal: si dx estuviera equivocado, un
    cuerpo se meteria dentro del otro y aca se veria.
    """
    avisos = []
    cajas = []
    for p in partes:
        xs = [n['x'] for n in p['nodos']]
        ys = [n['y'] for n in p['nodos']]
        cajas.append((p['info'].get('edificio'),
                      min(xs), max(xs), min(ys), max(ys)))

    for i in range(len(cajas)):
        for j in range(i + 1, len(cajas)):
            a, b = cajas[i], cajas[j]
            solape_x = min(a[2], b[2]) - max(a[1], b[1])
            solape_y = min(a[4], b[4]) - max(a[3], b[3])
            if solape_x > 0 and solape_y > 0:
                avisos.append(
                    'los cuerpos %s y %s se SOLAPAN en planta '
                    '(%.2f m en x por %.2f m en y). El calce esta mal.'
                    % (a[0], b[0], solape_x, solape_y))
            elif solape_y > 0:
                sep = -solape_x
                avisos.append(
                    'separacion entre %s y %s: %.3f m  (la junta declarada '
                    'esta en %s = %.3f)'
                    % (a[0], b[0], sep, junta.get('plano', 'x'),
                       junta.get('coord_en_el_marco', float('nan'))))
    return avisos, cajas


# ============================================================
def main():
    print('=' * 72)
    print(' ARMAR EL CONJUNTO   los dos cuerpos en un modelo')
    print('=' * 72)

    with io.open(CALCE, encoding='utf-8') as f:
        calce = json.load(f)

    print('  marco de referencia: %s' % calce['marco_de_referencia'])
    print()

    partes = []
    for i, (nombre, cfg) in enumerate(calce['edificios'].items()):
        m = modelo_de(cfg.get('archivo', nombre))
        partes.append(_remapear(m, nombre, cfg, (i + 1) * PASO_DE_TAG))

    print()
    print('  CALCE APLICADO')
    for nombre, cfg in calce['edificios'].items():
        print('    %-11s  dx = %+8.3f   dy = %+8.3f   giro = %.1f grados'
              % (nombre, cfg.get('dx', 0.0), cfg.get('dy', 0.0),
                 cfg.get('giro_grados', 0.0)))

    conjunto = unir(partes)

    avisos, cajas = revisar_la_junta(conjunto, partes, calce.get('junta', {}))
    print()
    print('  EN PLANTA, YA CALZADOS')
    for nombre, x0, x1, y0, y1 in cajas:
        print('    %-11s  x [%8.3f , %8.3f]   y [%8.3f , %8.3f]'
              % (nombre, x0, x1, y0, y1))
    print()
    for a in avisos:
        print('    %s' % a)

    problemas = contrato.validar(conjunto)
    if problemas:
        print()
        print('  El conjunto tiene %d problema(s):' % len(problemas))
        for p in problemas[:10]:
            print('    - %s' % p)
        return 1

    ruta = contrato.guardar_modelo(NOMBRE, conjunto)
    print()
    print('  %s' % contrato.resumen(conjunto))
    print('  validado: ninguna carga quedo apuntando a un tag inexistente')
    print('  -> %s  (%.2f MB)'
          % (os.path.relpath(ruta, rutas.RAIZ), os.path.getsize(ruta) / 1e6))
    print()
    print('  Sigue:  python comun/calcular.py %s' % NOMBRE)
    return 0


if __name__ == '__main__':
    sys.exit(main())
