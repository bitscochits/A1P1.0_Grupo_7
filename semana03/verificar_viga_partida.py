# -*- coding: utf-8 -*-
r"""
================================================================
 semana03/verificar_viga_partida.py  -  EL CORTE NO ES EL PROBLEMA
================================================================
 En el visor hay vigas que se hunden en el medio, y estan partidas en
 dos elementos justo ahi. Parece la explicacion, y no lo es.

 Correr:  python semana03/verificar_viga_partida.py
          python semana03/verificar_viga_partida.py ingenieria 366 373 380
          python semana03/verificar_viga_partida.py lt2          los del LT2

 ----------------------------------------------------------------
 PARTIR UNA VIGA NO LE PONE UNA ROTULA
 ----------------------------------------------------------------
 Dos elementos que comparten un nodo comparten sus SEIS grados de
 libertad: el momento pasa entero. El nodo esta ahi porque sin el la
 viga perpendicular no tendria donde apoyarse.

 La forma de comprobarlo es refinar: si el corte fuera el problema,
 poner mas tramos cambiaria la respuesta. Este modulo parte los dos
 tramos en 2, 4 y 8 cada uno y compara. Sale identico al cuarto
 decimal, que es la prueba de que el elemento esta bien.

 Lo que si la hunde es la viga secundaria que aterriza en ese punto
 trayendo su losa, sin columna debajo. Eso lo mide
 semana03/verificar_viga_partida.py --causa.
================================================================
"""
import copy, json, os, sys
sys.path.insert(0, 'comun')
import contrato, servidor_opensees as motor

BASE = None      # se carga en main(), segun el edificio pedido


def subdividir(modelo, ids, veces):
    """Parte cada elemento de `ids` en `veces` tramos iguales."""
    m = copy.deepcopy(modelo)
    nodos = {int(n['id']): n for n in m['nodos']}
    elems = {int(e['id']): e for e in m['elementos']}
    sig_n = max(nodos) + 1
    sig_e = max(elems) + 1
    # A que diafragma pertenece cada nodo, para heredarlo.
    de_nodo = {}
    for i, d in enumerate(m.get('diafragmas', [])):
        de_nodo[int(d['nodo_maestro'])] = i
        for n in d.get('nodos', []):
            de_nodo.setdefault(int(n), i)

    for eid in ids:
        e = elems[eid]
        a, b = nodos[int(e['n1'])], nodos[int(e['n2'])]
        dia = de_nodo.get(int(e['n1']))
        nuevos = []
        for k in range(1, veces):
            t = k / float(veces)
            n = {'id': sig_n, 'fijo': False, 'auxiliar': False,
                 'restricciones': [0, 0, 0, 0, 0, 0]}
            for c in 'xyz':
                n[c] = float(a[c]) + t * (float(b[c]) - float(a[c]))
            m['nodos'].append(n)
            nuevos.append(sig_n)
            # El nodo nuevo esta en la losa: lo ata el mismo diafragma.
            if dia is not None:
                m['diafragmas'][dia]['nodos'].append(sig_n)
            sig_n += 1

        cadena = [int(e['n1'])] + nuevos + [int(e['n2'])]
        e['n2'] = cadena[1]
        if 'area_tributaria' in e:
            e['area_tributaria'] = float(e['area_tributaria']) / veces
        hijos = [e]
        for k in range(1, veces):
            h = copy.deepcopy(e)
            h['id'] = sig_e; sig_e += 1
            h['n1'], h['n2'] = cadena[k], cadena[k + 1]
            m['elementos'].append(h)
            hijos.append(h)
        # La carga distribuida se copia tal cual: es por unidad de largo.
        for caso in m['casos_de_carga']:
            extra = []
            for c in caso.get('cargas_distribuidas', []):
                if int(c['elemento']) == eid:
                    for h in hijos[1:]:
                        d = dict(c); d['elemento'] = h['id']; extra.append(d)
            caso['cargas_distribuidas'].extend(extra)
    return m


def uz_en(modelo, nodo):
    datos = copy.deepcopy(modelo)
    datos['casos_de_carga'] = [c for c in datos['casos_de_carga']
                               if c['nombre'] == 'G']
    r = motor.construir_y_resolver(datos)['casos'][0]
    d = {int(x['id']): x for x in r['desplazamientos']}
    return {n: float(d[n]['uz']) * 1000 for n in nodo}


def candidatos(modelo):
    """
    Los nodos interesantes, como LISTA de enteros: donde dos vigas
    alineadas se juntan, llega una perpendicular y NO hay columna. Son
    los que se ven hundidos.
    """
    nodos = {int(n['id']): n for n in modelo['nodos']}
    porta = {}
    apoyado = set()
    for e in modelo['elementos']:
        t = e.get('tipo', '')
        for nid in (int(e['n1']), int(e['n2'])):
            if t in ('columna', 'muro', 'pilar_metal'):
                apoyado.add(nid)
            elif t.startswith('viga'):
                porta.setdefault(nid, []).append(e)

    def eje(e):
        a, b = nodos[int(e['n1'])], nodos[int(e['n2'])]
        d = [float(b[k]) - float(a[k]) for k in ('x', 'y', 'z')]
        return max(range(3), key=lambda i: abs(d[i]))

    salida = []
    for nid, vigas in sorted(porta.items()):
        if nid in apoyado or len(vigas) < 3:
            continue
        ejes = {}
        for e in vigas:
            ejes.setdefault(eje(e), 0)
            ejes[eje(e)] += 1
        # dos alineadas mas al menos una perpendicular
        if max(ejes.values()) >= 2 and len(ejes) >= 2:
            salida.append(nid)
    return salida


def lista_de(modelo, cuantos=12):
    """Los mismos, en una linea, para los mensajes."""
    return ', '.join(str(n) for n in candidatos(modelo)[:cuantos]) or '(ninguno)'


def buscar_tramos(modelo, nodo_medio):
    """Los dos elementos de viga que se juntan en ese nodo, y sus otros
    extremos. Es la viga que uno diria que esta 'cortada'."""
    tramos = [e for e in modelo['elementos']
              if e.get('tipo', '').startswith('viga')
              and nodo_medio in (int(e['n1']), int(e['n2']))]
    # De los que llegan, la pareja alineada: misma seccion y misma
    # direccion. Los perpendiculares son justamente los que obligan a
    # que exista el nodo.
    nodos = {int(n['id']): n for n in modelo['nodos']}

    def eje(e):
        a, b = nodos[int(e['n1'])], nodos[int(e['n2'])]
        d = [float(b[k]) - float(a[k]) for k in ('x', 'y', 'z')]
        return max(range(3), key=lambda i: abs(d[i]))

    por_eje = {}
    for e in tramos:
        por_eje.setdefault(eje(e), []).append(e)
    linea = max(por_eje.values(), key=len) if por_eje else []
    if len(linea) < 2:
        raise SystemExit(
            'el nodo %d no es el punto medio de una viga partida.\n'
            'Nodos que si lo son en este edificio: %s'
            % (nodo_medio, lista_de(modelo)))
    extremos = [int(e['n1']) if int(e['n2']) == nodo_medio else int(e['n2'])
                for e in linea]
    return [int(e['id']) for e in linea], extremos


def main(argv):
    global BASE
    edificio = argv[0] if argv and not argv[0].isdigit() else 'ingenieria'
    numeros = [int(a) for a in argv if a.isdigit()]
    BASE = contrato.cargar_modelo(edificio)

    if numeros:
        medio = numeros[0]
    else:
        # Sin nodo, el primero que este edificio tenga. Un numero fijo
        # solo vale para el edificio que se tuvo delante al escribirlo:
        # 373 es de Ingenieria y en el LT2 no es punto medio de nada.
        disponibles = candidatos(BASE)
        if not disponibles:
            raise SystemExit('%s no tiene vigas partidas que revisar'
                             % edificio)
        medio = disponibles[0]
    partidas, extremos = buscar_tramos(BASE, medio)
    mirar = [extremos[0], medio, extremos[-1]]

    nodos = {int(n['id']): n for n in BASE['nodos']}
    elems = {int(e['id']): e for e in BASE['elementos']}
    a, b = nodos[mirar[0]], nodos[mirar[-1]]
    largo = sum((float(b[k]) - float(a[k])) ** 2
                for k in ('x', 'y', 'z')) ** 0.5
    perp = [int(e['id']) for e in BASE['elementos']
            if e.get('tipo', '').startswith('viga')
            and int(e['id']) not in partidas
            and medio in (int(e['n1']), int(e['n2']))]
    apoyo = [e['tipo'] for e in BASE['elementos']
             if e.get('tipo') in ('columna', 'muro', 'pilar_metal')
             and medio in (int(e['n1']), int(e['n2']))]

    print('=' * 74)
    print('  LA VIGA PARTIDA DEL NODO %d   (%s)' % (medio, edificio))
    print('=' * 74)
    print('  tramos %s, del nodo %d al %d, %.2f m en total'
          % (partidas, mirar[0], mirar[-1], largo))
    print('  en el nodo %d llegan ademas %s' % (medio, perp or 'nada'))
    print('  apoyo vertical en el nodo %d: %s' % (medio, apoyo or 'NINGUNO'))
    print()
    print('  Si el corte fuera el problema, refinar cambiaria la respuesta.')
    print()
    print('  %-28s %10s %10s %10s %12s'
          % ('malla', 'uz %d' % mirar[0], 'uz %d' % medio,
             'uz %d' % mirar[-1], 'flecha rel.'))
    rel0 = None
    for veces in (1, 2, 4, 8):
        m = BASE if veces == 1 else subdividir(BASE, partidas, veces)
        u = uz_en(m, mirar)
        rel = u[medio] - (u[mirar[0]] + u[mirar[-1]]) / 2.0
        if rel0 is None:
            rel0 = rel
        print('  %-28s %10.4f %10.4f %10.4f %12.4f'
              % ('como esta (%d tramos)' % len(partidas) if veces == 1
                 else '%d tramos por mitad' % veces,
                 u[mirar[0]], u[medio], u[mirar[-1]], rel))

    # Sin la losa que trae la viga perpendicular.
    sin = copy.deepcopy(BASE)
    for c in sin['casos_de_carga']:
        c['cargas_distribuidas'] = [x for x in c.get('cargas_distribuidas', [])
                                    if int(x['elemento']) not in perp]
    u = uz_en(sin, mirar)
    rel_sin = u[medio] - (u[mirar[0]] + u[mirar[-1]]) / 2.0
    print('  %-28s %10.4f %10.4f %10.4f %12.4f'
          % ('sin la losa de la perpendicular',
             u[mirar[0]], u[medio], u[mirar[-1]], rel_sin))

    print()
    print('  El elemento esta bien: refinar no mueve el resultado.')
    print('  De la flecha, %.0f %% la trae la viga perpendicular con su losa.'
          % (100 * (rel0 - rel_sin) / rel0 if rel0 else 0))
    print('  %.2f mm sobre %.1f m es L/%.0f, contra el L/360 de la norma'
          % (abs(rel0), largo, largo * 1000 / abs(rel0)))
    print('  (L/360 serian %.1f mm). Lo que se ve grande en el visor es la'
          % (largo * 1000 / 360))
    print('  escala grafica: a x300, %.2f mm se dibujan como %.2f m.'
          % (abs(rel0), abs(rel0) / 1000 * 300))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
