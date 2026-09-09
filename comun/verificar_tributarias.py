# -*- coding: utf-8 -*-
r"""
================================================================
 comun/verificar_tributarias.py  -  LA LOSA LLEGA DONDE SE DIBUJA
================================================================
 Compara, para CADA edificio de data/modelo/, tres cosas que tienen
 que decir lo mismo:

     1. el area tributaria sellada en cada elemento
     2. los poligonos que dibuja data/unity/<edificio>.json
     3. la carga que los casos de gravedad aplican de verdad

 Correr:  python comun/verificar_tributarias.py
          python comun/verificar_tributarias.py lt2

 ----------------------------------------------------------------
 POR QUE HACE FALTA UNA VERIFICACION APARTE
 ----------------------------------------------------------------
 El equilibrio global NO detecta nada de esto. El equilibrio compara
 la carga APLICADA contra las reacciones, y si un pano de losa nunca
 entro al modelo, no esta en ninguno de los dos lados de esa resta:
 cierra perfecto con el edificio pesando menos de lo que pesa.

 Los tres modos de falla que se cazan aca aparecieron de verdad en
 este proyecto:

   - Carga sin dibujo. En el edificio de Ingenieria, 124 de 301 vigas
     recibian losa sin tener poligono. La carga estaba bien; lo que
     estaba mal era el recorrido de panos del exportador. Se veia
     como huecos blancos en el visor y nadie sabia si faltaba la
     carga o faltaba el dibujo.

   - Dibujo sin carga. El espejo del anterior: un poligono colgado de
     un elemento que ya no existe, que el visor dibuja flotando.

   - q implicito que no es constante. Si la carga de una barra y su
     area no dan la misma presion que las demas de SU PISO, entonces
     el reparto y el dibujo se contradicen aunque los dos por separado
     parezcan sanos. Es lo que delato que el corte geometrico de los
     panos discrepaba hasta un 40% del reparto de la carga.

 ----------------------------------------------------------------
 LA CARGA DISTRIBUIDA PUEDE TRAER EL PESO PROPIO ADENTRO
 ----------------------------------------------------------------
 En el caso G, lo que se aplica sobre una viga no es solo la losa:

     w  =  A_seccion * gamma   +   q * A_tributaria / L
           \_____________/         \_________________/
            peso de la viga          losa que le llega

 En Q no: ahi w es solo losa. Dividir el w de G por el area tributaria
 no da la presion de la losa, da un numero que ademas varia de barra
 en barra porque cada seccion pesa distinto.

 Cual de las dos formas es un caso lo dice el caso mismo, en
 'incluye_peso_propio'. Si no lo declara -- el edificio de Ingenieria
 todavia no lo hace -- se INFIERE probando las dos hipotesis y
 quedandose con la que deja el q constante dentro de cada piso, y se
 imprime que se infirio. Inferir esta bien; inferir en silencio no.

 La resta del peso propio es ademas CONDICIONAL: solo si w lo supera.
 Un brazo rigido tiene una seccion ficticia enorme -- 4x4 m, 400 kN/m
 -- que nunca se aplico como carga, porque su peso ya esta contado en
 el muro del que el brazo es un pedazo. Restarsela dejaria su q en
 negativo.

 ----------------------------------------------------------------
 EL q SE COMPARA DENTRO DE CADA PISO, NO ENTRE PISOS
 ----------------------------------------------------------------
 Un techo carga menos que un piso tipo, y eso es correcto: el plano
 de cargas del LT2 declara 500 kgf/m2 de sobrecarga hasta el piso 3
 y 300 en el techo. Comparar contra la mediana del edificio entero
 marcaria el techo completo como fallado. La constancia que TIENE
 que cumplirse es dentro de un mismo piso.

 Y por lo mismo el q por piso NO se revisa en un modelo que junta dos
 cuerpos: ahi un mismo nivel tiene losas de dos edificios con
 presiones distintas -- 6.30 kN/m2 el LT2 y 7.75 el de Ingenieria --
 y no hay ninguna razon para que coincidan. Cada cuerpo ya se revisa
 por su cuenta.
================================================================
"""
from __future__ import annotations

import io
import json
import math
import os
import sys

_AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _AQUI)

import contrato                              # noqa: E402
import rutas                                 # noqa: E402

# Cuanto puede desviarse el q implicito de una barra respecto de la
# mediana de SU PISO, en tanto por uno. Con el peso propio bien tratado
# los dos edificios dan cero barras fuera, asi que el 2% es margen de
# redondeo: los w viajan redondeados a 6 decimales y las areas a 6.
TOL_Q = 0.02

# Cuanto puede alejarse una carga de ser exactamente el peso propio de
# la barra para seguir considerandola "solo peso propio", en tanto por
# uno. Una viga sin losa encima aplica su peso y nada mas.
TOL_PESO_PROPIO = 1e-4

# Casos que reparten losa por area. Los laterales aplican fuerza en los
# nodos maestros y no tienen nada que ver con esto.
CASOS_DE_GRAVEDAD = ('G', 'Q')


def _largo(e, nodos):
    n1, n2 = nodos[int(e['n1'])], nodos[int(e['n2'])]
    return math.sqrt(sum((float(n2[k]) - float(n1[k])) ** 2
                         for k in ('x', 'y', 'z')))


def _cota(e, nodos):
    n1, n2 = nodos[int(e['n1'])], nodos[int(e['n2'])]
    return round((float(n1['z']) + float(n2['z'])) / 2.0, 2)


def _mediana(v):
    v = sorted(v)
    if not v:
        return 0.0
    mitad = len(v) // 2
    return v[mitad] if len(v) % 2 else (v[mitad - 1] + v[mitad]) / 2.0


def peso_propio_por_metro(e, secciones, gamma):
    """Lo que pesa un metro de esta barra, en kN/m."""
    s = secciones.get(e.get('seccion'))
    if not s:
        return 0.0
    return float(s.get('A', 0.0)) * gamma


def repartir(caso, elementos, nodos, secciones, gamma, con_area, restar_pp):
    """
    Recorre las cargas distribuidas de un caso y devuelve, por cota:
    los q implicitos de cada barra, los kN de losa aplicados y los m2
    que se le atribuyen. Devuelve tambien las cargas que no se explican
    y cuantas barras aplican solo su propio peso.
    """
    por_piso, losa, area = {}, {}, {}
    sin_explicar, solo_su_peso = [], 0

    for c in caso.get('cargas_distribuidas', []):
        t = int(c['elemento'])
        w = abs(float(c.get('wz', 0.0)))
        if w == 0.0 or t not in elementos:
            continue
        e = elementos[t]
        pp = peso_propio_por_metro(e, secciones, gamma)
        A = con_area.get(t, 0.0)

        if A <= 0:
            # Una viga sin losa encima aplica su peso y nada mas: eso
            # esta bien. Cualquier otra carga sin area detras es carga
            # que nadie puede dibujar ni justificar.
            if pp > 0 and abs(w - pp) <= TOL_PESO_PROPIO * max(pp, 1.0):
                solo_su_peso += 1
            else:
                sin_explicar.append(t)
            continue

        L = _largo(e, nodos)
        if L <= 1e-9:
            continue
        w_losa = w - pp if (restar_pp and w > pp) else w
        z = _cota(e, nodos)
        por_piso.setdefault(z, []).append((w_losa * L / A, t))
        losa[z] = losa.get(z, 0.0) + w_losa * L
        area[z] = area.get(z, 0.0) + A

    return por_piso, losa, area, sin_explicar, solo_su_peso


def _cuantas_fuera(por_piso):
    """Barras cuyo q se aparta de la mediana de su piso."""
    n = 0
    for valores in por_piso.values():
        q_piso = _mediana([q for q, _t in valores])
        n += sum(1 for q, _t in valores
                 if abs(q - q_piso) > TOL_Q * max(q_piso, 1e-9))
    return n


def revisar(nombre: str) -> list:
    """
    Revisa un edificio. Devuelve la lista de problemas; vacia si esta
    sano. Imprime el detalle por consola.
    """
    problemas = []
    modelo = contrato.cargar_modelo(nombre)
    nodos = {int(n['id']): n for n in modelo['nodos']}
    elementos = {int(e['id']): e for e in modelo['elementos']}
    secciones = {s['nombre']: s for s in modelo.get('secciones', [])}
    gamma = float(modelo.get('material', {}).get('gamma', 0.0) or 0.0)
    cuerpos = modelo.get('info', {}).get('cuerpos') or []

    con_area = {t: float(e[contrato.CAMPO_AREA])
                for t, e in elementos.items()
                if float(e.get(contrato.CAMPO_AREA, 0.0)) > 0}

    print('  %d de %d elementos reciben losa, %.2f m2 en total'
          % (len(con_area), len(elementos), sum(con_area.values())))

    if not con_area:
        problemas.append('%s: ningun elemento trae area tributaria; hay que '
                         'volver a armar el modelo' % nombre)
        return problemas

    # ---- 1. el modelo y su dibujo dicen lo mismo -------------------
    ruta_vista = rutas.unity(nombre)
    if os.path.isfile(ruta_vista):
        with io.open(ruta_vista, encoding='utf-8') as f:
            vista = json.load(f)
        del_dibujo = contrato.areas_por_elemento(vista)
        if del_dibujo:
            solo_modelo = sorted(set(con_area) - set(del_dibujo))
            solo_dibujo = sorted(set(del_dibujo) - set(con_area))
            peor, cual = 0.0, None
            for t in set(con_area) & set(del_dibujo):
                if abs(con_area[t] - del_dibujo[t]) > peor:
                    peor, cual = abs(con_area[t] - del_dibujo[t]), t
            print('     dibujo: %d elementos, %.2f m2; peor diferencia %.6f m2'
                  % (len(del_dibujo), sum(del_dibujo.values()), peor))
            if solo_modelo:
                problemas.append(
                    '%s: %d elemento(s) reciben losa sin tener poligono (el '
                    'visor los deja como hueco blanco): %s'
                    % (nombre, len(solo_modelo), solo_modelo[:8]))
            if solo_dibujo:
                problemas.append(
                    '%s: %d poligono(s) dibujados sobre elementos sin area '
                    'sellada: %s' % (nombre, len(solo_dibujo), solo_dibujo[:8]))
            if peor > contrato.TOL_AREA_M2:
                problemas.append(
                    '%s: el elemento %d tiene %.4f m2 en el modelo y %.4f m2 '
                    'en el dibujo' % (nombre, cual, con_area[cual],
                                      del_dibujo[cual]))
    else:
        print('     (no hay data/unity/%s.json: no se compara con el dibujo)'
              % nombre)

    # ---- 2. y 3. la carga contra el area, piso por piso ------------
    for caso in modelo.get('casos_de_carga', []):
        if caso.get('nombre') not in CASOS_DE_GRAVEDAD:
            continue
        etiqueta = caso['nombre']

        comun = (elementos, nodos, secciones, gamma, con_area)
        declarado = caso.get(contrato.CAMPO_PESO_PROPIO)
        if declarado is not None:
            restar, origen = bool(declarado), 'declarado'
        else:
            # Se prueban las dos y gana la que deja el q constante
            # dentro de cada piso. El empate se resuelve por la
            # hipotesis simple: la carga es solo losa.
            con_resta = repartir(caso, *comun, restar_pp=True)
            sin_resta = repartir(caso, *comun, restar_pp=False)
            restar = _cuantas_fuera(con_resta[0]) < _cuantas_fuera(sin_resta[0])
            origen = 'inferido'

        por_piso, losa, area, sin_explicar, solo_su_peso = repartir(
            caso, *comun, restar_pp=restar)

        if not por_piso:
            continue

        if sin_explicar:
            problemas.append(
                '%s, caso %s: %d elemento(s) reciben carga que no es losa ni '
                'su propio peso: %s' % (nombre, etiqueta, len(sin_explicar),
                                        sorted(sin_explicar)[:8]))

        print('     caso %s   peso propio en la carga distribuida: %s (%s)%s'
              % (etiqueta, 'SI' if restar else 'no', origen,
                 ('   %d barra(s) aplican solo su peso propio' % solo_su_peso)
                 if solo_su_peso else ''))

        # La tabla de abajo solo cuenta lo que baja REPARTIDO. La losa
        # que se apoya directo sobre un muro va como carga puntual en su
        # baricentro, asi que su area no aparece en ninguna fila. Sin
        # decirlo, las columnas no suman el total del encabezado y quien
        # mire va a creer que falta losa.
        repartida = sum(area.values())
        puntual = sum(con_area.values()) - repartida
        if puntual > contrato.TOL_AREA_M2:
            print('        %.2f m2 bajan repartidos y %.2f m2 como carga '
                  'puntual sobre muros' % (repartida, puntual))

        if len(cuerpos) > 1:
            print('        (%s junta %s: el q por piso mezcla dos losas y no '
                  'se compara)' % (nombre, ' y '.join(cuerpos)))
            continue

        print('        %-8s %5s %12s %14s %12s'
              % ('cota', 'n', 'q [kN/m2]', 'losa [kN]', 'area [m2]'))
        for z in sorted(por_piso):
            valores = [q for q, _t in por_piso[z]]
            q_piso = _mediana(valores)
            fuera = [(q, t) for q, t in por_piso[z]
                     if abs(q - q_piso) > TOL_Q * max(q_piso, 1e-9)]
            print('        %+8.2f %5d %12.4f %14.2f %12.2f   %s'
                  % (z, len(valores), q_piso, losa[z], area[z],
                     '' if not fuera else '<-- %d fuera del %.0f%%'
                     % (len(fuera), TOL_Q * 100)))
            for q, t in sorted(fuera, key=lambda p: -abs(p[0] - q_piso))[:5]:
                print('            elemento %d: q = %.4f kN/m2 (%.1f%% del piso)'
                      % (t, q, 100.0 * q / max(q_piso, 1e-9)))
            if fuera:
                problemas.append(
                    '%s, caso %s, cota %+.2f: %d barra(s) con q implicito '
                    'fuera del %.0f%% de %.4f kN/m2'
                    % (nombre, etiqueta, z, len(fuera), TOL_Q * 100, q_piso))

            # La conservacion que pide el laboratorio:  suma = q * A.
            # Es identidad si todas las barras del piso dan el mismo q,
            # que es justo lo que se acaba de comprobar; se calcula
            # igual porque es EL numero que hay que mostrar.
            esperado = q_piso * area[z]
            if abs(esperado - losa[z]) > 1e-3 * max(esperado, 1.0):
                problemas.append(
                    '%s, caso %s, cota %+.2f: la losa aplicada suma %.4f kN '
                    'pero q*A da %.4f kN'
                    % (nombre, etiqueta, z, losa[z], esperado))

    return problemas


def main(cuales=None):
    carpeta = os.path.dirname(rutas.modelo('x'))
    disponibles = sorted(os.path.splitext(f)[0]
                         for f in os.listdir(carpeta) if f.endswith('.json'))
    nombres = list(cuales) if cuales else disponibles

    print('=' * 68)
    print('  AREAS TRIBUTARIAS: EL MODELO CONTRA SU DIBUJO')
    print('=' * 68)

    problemas = []
    for nombre in nombres:
        print('\n%s' % nombre)
        if nombre not in disponibles:
            problemas.append('no existe data/modelo/%s.json' % nombre)
            print('  no existe data/modelo/%s.json' % nombre)
            continue
        problemas += revisar(nombre)

    print('\n' + '=' * 68)
    if problemas:
        print('  %d PROBLEMA(S)' % len(problemas))
        for p in problemas:
            print('    - %s' % p)
        print('=' * 68)
        return 1
    print('  TODO CALZA: la losa que se aplica es la que se dibuja')
    print('=' * 68)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
