# Semana 3

Esta entrega reutiliza el modelo existente del Edificio de Ingenieria. No
reconstruye la geometria: lee `data/modelo/ingenieria.json`, los resultados
guardados y usa el motor comun de OpenSees en memoria.

## Demanda

- **G**: peso propio y cargas permanentes.
- **Q**: carga viva. Para cada viga, `Q_i = q_Q A_i`; por tanto,
  `sum(Q_i) = q_Q sum(A_i)`.
- **EX/EY**: sismo pseudoestatico independiente. La demostracion usa
  `W_i = G_i + 0.5 Q_i`, el `Cs` existente (`0.10`) y la distribucion
  `F_i = V W_i h_i / sum(W_j h_j)`, aplicada en los maestros de diafragma.

El JSON historico del proyecto no incluia `0.5 Q` en el peso sismico. La
correccion se hace localmente en `lab_semana03.py`; no modifica la geometria,
los JSON ni los resultados existentes.

## Superposicion

Se compara la combinacion `1.0 G + 0.5 Q + 1.0 EX` de dos maneras: sumando
resultados independientes y ejecutando una corrida explicita con las cargas
combinadas. Como el modelo es lineal elastico, `K u = F`, de modo que
`u(lambda F) = lambda u(F)`. Esta igualdad no se debe extender a modelos no
lineales.

## Capacidad

`capacidad_ha.py` estudia una columna de 0.50 x 0.50 m, consistente con el
modelo global. La armadura no aparece en los datos del proyecto, por lo que
se usa un **SUPUESTO DE LABORATORIO - NO EXTRAIDO DE PLANOS**: diez barras de
20 mm, recubrimiento de 50 mm y acero de 420 MPa.

La Fiber Section asigna una deformacion a cada fibra:
`epsilon(y) = epsilon_0 - phi y`. Luego integra `P = sum(sigma A)` y
`M = sum(sigma A y)`. Se generan las curvas M-phi y P-M en `resultados/`.

## Ejecucion

Desde la raiz del repositorio:

```powershell
python semana03\lab_semana03.py
python semana03\capacidad_ha.py
```

La primera orden verifica carga viva, sismo y superposicion. La segunda crea:

- `semana03/resultados/momento_curvatura.png`
- `semana03/resultados/interaccion_PM.png`

Las cargas G, Q, EX, EY y sus combinaciones representan **demanda**. Fiber
Section, M-phi e interaccion P-M representan **capacidad** de una seccion
aislada, no una modificacion del modelo global.
