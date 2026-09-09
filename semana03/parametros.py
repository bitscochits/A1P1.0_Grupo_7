# -*- coding: utf-8 -*-
r"""
================================================================
 semana03/parametros.py  -  LO QUE DEFINE EL PROFESOR
================================================================
 Los valores viven en parametros.json, al lado. Este modulo los lee y
 los deja disponibles de dos formas:

   1. como constantes de modulo, igual que antes:

        from parametros import q_Q, coef_sismico, lambda_G, ...

   2. como un diccionario que se puede sobreescribir por linea de
      comandos, que es lo que sirve si el profesor dicta numeros
      durante la demostracion:

        p = parametros.cargar(sys.argv)
        python semana03/lab.py --q 2.5 --cs 0.15 --comb 1.2 1.6 1.0 0.3
        python semana03/lab.py --patron manual --fracciones 5 10 20 30 35

 ----------------------------------------------------------------
 POR QUE NO BASTA CON EDITAR UN .py
 ----------------------------------------------------------------
 El enunciado pide que el codigo pueda acomodar CUALQUIER solicitud.
 Con los valores escritos en Python, cambiarlos en vivo significa
 abrir un archivo, editarlo sin equivocarse, guardarlo y volver a
 correr, delante del profesor. Con --q y --cs es un argumento.

 Y separar el valor de su justificacion importa: el JSON puede
 explicar de donde sale cada numero sin que eso ensucie el codigo.

 ----------------------------------------------------------------
 LAS CONSTANTES SIGUEN EXISTIENDO
 ----------------------------------------------------------------
 lab_semana03.py importa q_Q, coef_sismico, fraccion_Q_sismica, los
 cuatro lambda_* y los tres del PATRON sismico. Siguen ahi y valen lo
 mismo que antes -- la combinacion 'S3' del JSON es la que estaba
 escrita en este archivo -- asi que ese script no cambia ni sus
 resultados tampoco.

 ----------------------------------------------------------------
 EL PATRON EN ALTURA
 ----------------------------------------------------------------
 'potencia' reparte la fuerza como  W_i * h_i^k :

     k = 0   uniforme, solo la masa
     k = 1   triangular invertido, el clasico
     k = 2   tope de NCh433 / ASCE 7

 'manual' usa las fracciones que se le den, de abajo hacia arriba, y
 las normaliza solas para sumar 1 -- se pueden entregar como
 porcentajes o como pesos crudos. Entre los dos cubren cualquier
 reparto que pida el profesor, que es lo que exige el enunciado.
================================================================
"""
from __future__ import annotations

import io
import json
import os

_AQUI = os.path.dirname(os.path.abspath(__file__))
ARCHIVO = os.path.join(_AQUI, 'parametros.json')

# Si el JSON no esta, se cae a estos valores para no dejar de correr.
POR_DEFECTO = {
    'q_Q': 2.0,
    'coef_sismico': 0.10,
    'fraccion_Q_sismica': 0.50,
    'patron_sismico': 'potencia',
    'k_patron': 1.0,
    'fracciones_patron': None,
    'combinacion': {'nombre': 'S3', 'G': 1.0, 'Q': 0.5, 'EX': 1.0, 'EY': 0.0},
    'combinaciones': [],
}

CASOS = ('G', 'Q', 'EX', 'EY')
PATRONES = ('potencia', 'manual')


def _leer(ruta=ARCHIVO):
    if not os.path.isfile(ruta):
        return dict(POR_DEFECTO)
    with io.open(ruta, encoding='utf-8') as f:
        d = json.load(f)
    combos = [c for c in d.get('combinaciones', []) if 'nombre' in c]
    nombre = d.get('combinacion_por_defecto')
    elegida = next((c for c in combos if c['nombre'] == nombre),
                   combos[0] if combos else POR_DEFECTO['combinacion'])
    return {
        'q_Q': float(d.get('carga_viva', {}).get('q_kNm2',
                                                 POR_DEFECTO['q_Q'])),
        'coef_sismico': float(d.get('sismo', {}).get(
            'coeficiente', POR_DEFECTO['coef_sismico'])),
        'fraccion_Q_sismica': float(d.get('sismo', {}).get(
            'fraccion_Q', POR_DEFECTO['fraccion_Q_sismica'])),
        'patron_sismico': str(d.get('sismo', {}).get(
            'patron', POR_DEFECTO['patron_sismico'])),
        'k_patron': float(d.get('sismo', {}).get(
            'k', POR_DEFECTO['k_patron'])),
        'fracciones_patron': d.get('sismo', {}).get('fracciones'),
        'combinacion': dict(elegida),
        'combinaciones': combos,
    }


def validar(p):
    """
    Rechaza lo que no tiene sentido fisico. Vale la pena aunque los
    valores vengan de un archivo: un q negativo o una fraccion mayor
    que uno no dan error en ninguna parte, dan resultados.
    """
    if p['q_Q'] < 0:
        raise ValueError('q_Q no puede ser negativo')
    if p['coef_sismico'] < 0:
        raise ValueError('el coeficiente sismico no puede ser negativo')
    if not 0.0 <= p['fraccion_Q_sismica'] <= 1.0:
        raise ValueError('la fraccion de Q para el peso sismico va entre '
                         '0 y 1')
    if p['patron_sismico'] not in PATRONES:
        raise ValueError('patron_sismico = %r; solo vale %s'
                         % (p['patron_sismico'], ' o '.join(PATRONES)))
    if p['patron_sismico'] == 'potencia' and p['k_patron'] < 0:
        raise ValueError('el exponente del patron no puede ser negativo')
    if p['patron_sismico'] == 'manual':
        f = p['fracciones_patron']
        if not f:
            raise ValueError("el patron 'manual' necesita fracciones")
        if any(float(x) < 0 for x in f):
            raise ValueError('las fracciones del patron no admiten '
                             'negativos')
    return p


def cargar(argv=None, ruta=ARCHIVO):
    """
    Los parametros, con lo que venga por linea de comandos encima.

        --q  <kN/m2>              sobrecarga de uso
        --cs <fraccion>           coeficiente sismico
        --fq <fraccion>           cuanta Q entra al peso sismico
        --comb <G> <Q> <EX> <EY>  factores de la combinacion
        --combinacion <nombre>    una de las declaradas en el JSON

    Los argumentos que no reconoce los ignora, para poder convivir con
    los de cada script.
    """
    p = _leer(ruta)
    a = list(argv or [])

    def numero(bandera):
        if bandera in a:
            i = a.index(bandera)
            try:
                return float(a[i + 1])
            except (IndexError, ValueError):
                raise SystemExit('%s necesita un numero' % bandera)
        return None

    v = numero('--q')
    if v is not None:
        p['q_Q'] = v
    v = numero('--cs')
    if v is not None:
        p['coef_sismico'] = v
    v = numero('--fq')
    if v is not None:
        p['fraccion_Q_sismica'] = v

    if '--patron' in a:
        i = a.index('--patron')
        p['patron_sismico'] = a[i + 1] if i + 1 < len(a) else ''
    v = numero('--k')
    if v is not None:
        p['k_patron'] = v
    if '--fracciones' in a:
        i = a.index('--fracciones')
        f = []
        for x in a[i + 1:]:
            try:
                f.append(float(x))
            except ValueError:
                break
        if not f:
            raise SystemExit('--fracciones necesita al menos un numero')
        p['fracciones_patron'] = f
        p['patron_sismico'] = 'manual'

    if '--combinacion' in a:
        i = a.index('--combinacion')
        nombre = a[i + 1] if i + 1 < len(a) else ''
        elegida = next((c for c in p['combinaciones']
                        if c['nombre'] == nombre), None)
        if elegida is None:
            raise SystemExit(
                'no existe la combinacion %r. Declaradas: %s'
                % (nombre, ', '.join(c['nombre'] for c in p['combinaciones'])))
        p['combinacion'] = dict(elegida)

    if '--comb' in a:
        i = a.index('--comb')
        try:
            f = [float(x) for x in a[i + 1:i + 5]]
        except (IndexError, ValueError):
            raise SystemExit('--comb necesita cuatro numeros: G Q EX EY')
        if len(f) < 4:
            raise SystemExit('--comb necesita cuatro numeros: G Q EX EY')
        p['combinacion'] = dict(zip(CASOS, f))
        p['combinacion']['nombre'] = 'a mano'

    return validar(p)


def factores(combinacion):
    """Solo los cuatro factores, sin el nombre ni los comentarios."""
    return {c: float(combinacion.get(c, 0.0)) for c in CASOS}


def como_texto(combinacion):
    """'1.20 G + 1.60 Q + 1.00 EX' -- sin los terminos en cero."""
    partes = ['%.2f %s' % (v, c)
              for c, v in factores(combinacion).items() if abs(v) > 1e-12]
    return ' + '.join(partes) if partes else '(nula)'


def describir(p):
    if p['patron_sismico'] == 'manual':
        patron = 'manual %s' % (p['fracciones_patron'],)
    else:
        patron = 'potencia, k = %.2f' % p['k_patron']
    L = ['q_Q                 = %.4f kN/m2' % p['q_Q'],
         'coeficiente sismico = %.4f' % p['coef_sismico'],
         'fraccion de Q       = %.2f' % p['fraccion_Q_sismica'],
         'patron en altura    = %s' % patron,
         'combinacion %-8s= %s' % ('(%s)' % p['combinacion'].get('nombre', ''),
                                   como_texto(p['combinacion']))]
    return '\n'.join('  ' + x for x in L)


# ============================================================
# Las constantes de siempre, para el codigo que ya las importa.
# ============================================================
_P = _leer()
q_Q = _P['q_Q']
coef_sismico = _P['coef_sismico']
fraccion_Q_sismica = _P['fraccion_Q_sismica']
patron_sismico = _P['patron_sismico']
k_patron = _P['k_patron']
fracciones_patron = _P['fracciones_patron']

_C = factores(_P['combinacion'])
lambda_G = _C['G']
lambda_Q = _C['Q']
lambda_EX = _C['EX']
lambda_EY = _C['EY']


if __name__ == '__main__':
    import sys
    p = cargar(sys.argv[1:])
    print('PARAMETROS DE LA SEMANA 3')
    print(describir(p))
    if p['combinaciones']:
        print()
        print('  combinaciones declaradas:')
        for c in p['combinaciones']:
            print('    %-18s %s' % (c['nombre'], como_texto(c)))
