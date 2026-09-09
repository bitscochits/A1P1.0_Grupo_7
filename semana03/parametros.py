# ==========================================================
# PARAMETROS ENTREGADOS POR EL PROFESOR
# ==========================================================

# Parte A — Carga viva
q_Q = 2.0                     # kN/m2

# Parte B — Sismo
coef_sismico = 0.10           # Cs
fraccion_Q_sismica = 0.50     # fracción de Q incluida en peso sísmico

# Patrón de distribución de la fuerza lateral en altura.
#
#   "potencia"  F_i proporcional a  W_i * h_i**k_patron
#                 k = 0  -> uniforme, solo la masa
#                 k = 1  -> triangular invertido clásico
#                 k = 2  -> límite superior de NCh433 / ASCE 7
#   "manual"    se usan las fracciones de fracciones_patron, de abajo
#               hacia arriba. Se normalizan solas para sumar 1, así que
#               pueden entregarse como porcentajes o como pesos crudos.
#
# Cualquier reparto que pida el profesor se cubre con uno de los dos.
patron_sismico = "potencia"
k_patron = 1.0
fracciones_patron = None      # p.ej. [0.05, 0.10, 0.20, 0.30, 0.35]

# Parte C — Superposición
lambda_G = 1.0
lambda_Q = 0.5
lambda_EX = 1.0
lambda_EY = 0.0

# q_Q = 2.0 y coef_sismico = 0.10 corresponden a los valores actuales de
# trabajo del modelo. No representan necesariamente los valores definitivos
# de la actividad: deben reemplazarse si el profesor entrega otros valores.
# Modificar este archivo no modifica el benchmark original.
