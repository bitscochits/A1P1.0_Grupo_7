# Chuleta — la demostración, en orden

La guía completa del repo, con el entorno, el flujo y todos los comandos,
está en [`reports/mapa_del_repo.md`](../reports/mapa_del_repo.md). Esto es
solo la secuencia de la interrogación, para tener a mano.

Si no activaste el entorno, `python` es `.\.venv\Scripts\python.exe`.

---

**Todo de una, antes de empezar** — termina en `27 de 27 EN OK`, ~25 s

    python comun\verificar_todo.py

**Partes A, B y C** — carga viva, sismo y superposición

    python semana03\lab_semana03.py
    python semana03\lab_semana03.py lt2
    python semana03\lab_semana03.py conjunto

**Si el profesor dicta parámetros** — no se edita nada, van como argumentos

    python semana03\lab_semana03.py --q 2.5 --cs 0.20
    python semana03\lab_semana03.py --k 2                    reparto NCh433
    python semana03\lab_semana03.py --k 0                    uniforme
    python semana03\lab_semana03.py --patron manual --fracciones 5 10 20 30 35
    python semana03\lab_semana03.py --comb 1.2 1.0 1.4 0

**Parte D** — la sección: discretización, M-φ y P-M interpretada

    python comun\capacidad.py ingenieria 18 --pm --mphi --dibujo

**Parte D** — la demanda sobre su propia curva

    python semana03\demanda_capacidad.py ingenieria 18 --grafico --mphi
    python semana03\demanda_capacidad.py ingenieria --todas

**Parte D** — las fibras contra el cálculo a mano

    python semana03\verificar_rc.py ingenieria 18

**Si preguntan por la torsión**

    python comun\sismo.py ingenieria EY --detalle

**Si preguntan por la superposición**

    python comun\combinar.py ingenieria

**Si preguntan por las vigas hundidas**

    python semana03\verificar_viga_partida.py

**El visor**

    python semana03\exportar_unity.py ingenieria
    python comun\lanzar_unity.py app ingenieria

---

## Los cuatro números

| | |
| --- | --- |
| A | 4320.65 m², 8641.30 kN; reacciones a `2e-8` |
| B | V = 5497.28 kN; torsión **extrema** bajo EY en los 3 pisos altos |
| C | 9102 valores comparados, todos bajo la cota de redondeo |
| D | columna 18: 16 φ16, cuantía 1.29 %, nariz en 2478 kN / 427 kN·m |

## Tres respuestas que van a pedir

- **`sum(Q) = q·A` es identidad**, así se construyó. Lo que verifica es que
  la carga llegue entera al suelo (reacciones a `2e-8`) y que la
  construcción cubra toda la losa.
- **La viga hundida no está cortada**: refinar de 2 a 16 tramos da lo mismo
  al cuarto decimal. Son 6.55 mm sobre 10 m, `L/1527`. Lo que se ve es la
  escala gráfica ×300.
- **No hay cuadro de pilares** en las 38 láminas: el sistema son muros. La
  armadura sale del detalle típico de la lámina `-000`; solo el diámetro
  φ16 es supuesto.
