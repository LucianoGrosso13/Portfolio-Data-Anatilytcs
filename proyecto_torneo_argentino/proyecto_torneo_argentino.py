import pandas as pd
from ortools.linear_solver import pywraplp

# Cargar datos desde archivos CSV
promedios_df = pd.read_csv('promedios.csv')
fixture_df = pd.read_csv('fixture.csv')

M = 1000

# Listas de fechas y fechas según los datos del fixture
fechas_unicas = sorted(fixture_df['fecha'].unique().astype(int).tolist())

fechas = list(zip(fixture_df['local'], fixture_df['visitante'], fixture_df['fecha'])) 
equipos = list(promedios_df['Equipo'])
puntos_actuales = list(zip(promedios_df['Equipo'], promedios_df['24']))
promedios = list(zip(promedios_df['Equipo'],promedios_df['Pts'], promedios_df['PJ'] + len(fechas_unicas)))

resultados_individuales = []

for equipo_a_salvar in equipos:

    solver = pywraplp.Solver.CreateSolver('SCIP')

    #equipo_a_salvar = 'Sarmiento (J)'

    # Definicion de las variabless Victoria i,f, Empate i,f

    victoria = {} 
    empate = {}

    for fecha in fechas:
        equipo_local = fecha[0]
        equipo_visitante = fecha[1]
        numero_fecha = fecha[2]

        victoria[(equipo_local, numero_fecha)] = solver.BoolVar(f'Victoria de {equipo_local} en la fecha {numero_fecha}')
        empate[(equipo_local, numero_fecha)] = solver.BoolVar(f'Empate de {equipo_local} en la fecha {numero_fecha}')

        victoria[(equipo_visitante, numero_fecha)] = solver.BoolVar(f'Victoria de {equipo_visitante} en la fecha {numero_fecha}')
        empate[(equipo_visitante, numero_fecha)] = solver.BoolVar(f'Empate de {equipo_visitante} en la fecha {numero_fecha}')


    # Definicion y calculo de la variable puntos en fecha

    puntos_en_fecha = {}
    for equipo_local, equipo_visitante, numero_fecha in fechas:

        puntos_en_fecha[(equipo_local, numero_fecha)] = solver.IntVar(0, 3, f'puntos de {equipo_local} en la fecha {numero_fecha}')
        puntos_en_fecha[(equipo_visitante, numero_fecha)] = solver.IntVar(0, 3, f'puntos de {equipo_visitante} en la fecha {numero_fecha}')

        # Calcular puntos para el equipo local y visitante
        p_local = 3 * victoria[(equipo_local, numero_fecha)] + empate[(equipo_local, numero_fecha)]
        p_visitante = 3 * victoria[(equipo_visitante, numero_fecha)] + empate[(equipo_visitante, numero_fecha)]

        solver.Add(puntos_en_fecha[(equipo_local, numero_fecha)] == p_local)
        solver.Add(puntos_en_fecha[(equipo_visitante, numero_fecha)] == p_visitante)


    # Definicion y calculo de la variable puntos acumulados

    puntos_acumulados = {}
    for equipo in equipos:
        puntos_acumulados[equipo] = solver.IntVar(0, solver.infinity(), f'puntos acumulados de {equipo}')

        p = solver.Sum([puntos_en_fecha[(equipo, numero_fecha)] for numero_fecha in fechas_unicas])
        solver.Add(puntos_acumulados[equipo] == p)


    #Definicion de la variable total_anual (puntos totales del equipo tomando los que ya tiene + los de la fechas que faltan)

    total_anual = {} 
    for equipo, pts_temporada_24 in puntos_actuales:

        total_anual[equipo] = solver.IntVar(0, solver.infinity(), f'puntos totales de {equipo}')

        solver.Add(total_anual[equipo] == pts_temporada_24 + puntos_acumulados[equipo])


    # Definicion de la variable promedio_temporadas (promedio de las ultimas 3 temporadas considerando los resultados de las fechas que quedan)

    promedio_temporadas = {}

    for equipo, pts, pj in promedios:

        promedio_temporadas[equipo] = solver.NumVar(0,solver.infinity(), f'promedio final de {equipo}')

        solver.Add(promedio_temporadas[equipo] == (pts + puntos_acumulados[equipo]) / pj)


    # Definicion y calculo de la variable W_tabla (1 Si el equipo tiene mas puntos que otro al final de la temporada. 0 sino)

    W_tabla = {}

    for equipo in equipos:
        for equipo2 in equipos:
            if equipo2 != equipo:
                W_tabla[equipo, equipo2] = solver.BoolVar(f'{equipo} tiene mas puntos que {equipo2}')

                solver.Add(total_anual[equipo] - total_anual[equipo2] <= M * W_tabla[equipo, equipo2])
                solver.Add(total_anual[equipo] - total_anual[equipo2] >= 1 - M * (1 - W_tabla[equipo, equipo2]))


    # Definicion y calculo de la variable W_promedio (1 Si el equipo tiene mas promedio que otro al final de la temporada. 0 sino)

    W_promedio = {}

    for equipo in equipos:
        for equipo2 in equipos:
            if equipo2 != equipo:
                W_promedio[equipo, equipo2] = solver.BoolVar(f'{equipo} tiene mas promedio que {equipo2}')

                solver.Add(promedio_temporadas[equipo] - promedio_temporadas[equipo2] <= M * W_promedio[equipo, equipo2])
                solver.Add(promedio_temporadas[equipo] - promedio_temporadas[equipo2] >= 0.000001 - M * (1 - W_promedio[equipo, equipo2])) # se usa un epsilon para evitar ambiguedades en el caso que los promedios sean iguales


    # Definicion variable B_tabla. 1 si la sumatoria de W_tabla para cada equipo <= 1. 0 sino

    B_tabla = {}
    for equipo in equipos:
        B_tabla[equipo] = solver.BoolVar(f'{equipo} desciende por tabla anual')

        suma_W_tabla = solver.Sum([W_tabla[equipo, equipo2] for equipo2 in equipos if equipo2 != equipo])

        solver.Add(suma_W_tabla <= 1 + M * (1 - B_tabla[equipo]))
        solver.Add(suma_W_tabla >= 1 - M * B_tabla[equipo])


    # Definicion de la variable W_promedio_ajustado que vale 1 solo si W_promedio es 1 Y B_tabla es 0. Esto "filtra" los equipos que ya descienden por tabla para el calculo de quienes descienden por promedio.

    W_promedio_ajustado = {}
    for equipo in equipos:
        for equipo2 in equipos:
            if equipo2 != equipo:
                W_promedio_ajustado[equipo, equipo2] = solver.BoolVar(f'W_promedio_ajustado_{equipo}_{equipo2}')
                
                # W_promedio_ajustado solo puede ser 1 si W_promedio es 1 Y B_tabla es 0
                solver.Add(W_promedio_ajustado[equipo, equipo2] <= W_promedio[equipo, equipo2])
                solver.Add(W_promedio_ajustado[equipo, equipo2] <= 1 - B_tabla[equipo2])
                solver.Add(W_promedio_ajustado[equipo, equipo2] >= W_promedio[equipo, equipo2] - B_tabla[equipo2])


    # Definicion variable B_promedio. 1 si la sumatoria de W_promedio_ajustado para cada equipo <= 1. 0 sino

    B_promedio = {}
    for equipo in equipos:
        B_promedio[equipo] = solver.BoolVar(f'{equipo} desciende por promedio')

        suma_W_promedio_ajustado = solver.Sum([W_promedio_ajustado[equipo, equipo2] for equipo2 in equipos if equipo2 != equipo])

        solver.Add(suma_W_promedio_ajustado <= 1 + M * (1 - B_promedio[equipo]))
        solver.Add(suma_W_promedio_ajustado >= 1 + 0.000001 - M * B_promedio[equipo])


    #### Restricciones

    for equipo_local, equipo_visitante, numero_fecha in fechas:

        # Un resultado por partido
        solver.Add(victoria[(equipo_local, numero_fecha)] + empate[(equipo_local, numero_fecha)] <= 1, f'Restriccion un resultado entre {equipo_local} y {equipo_visitante} para la fecha {numero_fecha}')

        # Dependencia de resultado
        solver.Add(victoria[(equipo_local, numero_fecha)] + victoria[(equipo_visitante, numero_fecha)] + empate[(equipo_local, numero_fecha)] == 1, f'Restriccion dependencia de resultado entre {equipo_local} y {equipo_visitante} para la fecha {numero_fecha}')

        # Si empata i empata j
        solver.Add(empate[(equipo_local, numero_fecha)] - empate[(equipo_visitante, numero_fecha)] == 0, f'Restriccion empatan {equipo_local} y {equipo_visitante} en la fecha {numero_fecha}')


    # No pueden descender los mismos por tabla y promedio

    for equipo in equipos:
        solver.Add(B_tabla[equipo] + B_promedio[equipo] <= 1)

    # Obligo al descenso de mi equipo a salvar por tabla o promedio

    solver.Add(B_tabla[equipo_a_salvar] + B_promedio[equipo_a_salvar] == 1)

    # Asegurar que haya exactamente 2 equipos que desciendan por tabla y 2 por promedio
    solver.Add(solver.Sum([B_tabla[equipo] for equipo in equipos]) == 2)
    solver.Add(solver.Sum([B_promedio[equipo] for equipo in equipos]) == 2)


    #### Funcion objetivo

    solver.Maximize(total_anual[equipo_a_salvar])

    status = solver.Solve()

    ## print con solucion completa

    if status == pywraplp.Solver.OPTIMAL:
        # Valor de la FO
        print(f"Valor de la FO: {solver.Objective().Value()}")

        # Calcular los puntos actuales de cada equipo
        puntos_equipos = {
            equipo: total_anual[equipo].solution_value()
            for equipo in equipos
        }
        
        # Ordenar equipos por puntos de menor a mayor
        equipos_ordenados_por_puntos = sorted(
            puntos_equipos.items(),
            key=lambda x: x[1]
        )
        
        # Encontrar la posición del equipo en la lista ordenada
        posicion_equipo = next(
            i for i, (equipo, _) in enumerate(equipos_ordenados_por_puntos)
            if equipo == equipo_a_salvar
        )
        
        # Obtener los puntos actuales del equipo a salvar directamente del DataFrame
        pts_temporada_24 = promedios_df.loc[promedios_df['Equipo'] == equipo_a_salvar, '24'].iloc[0]
        
        # Determinar los puntos límite del siguiente equipo
        puntos_limite = equipos_ordenados_por_puntos[posicion_equipo + 1][1]
        puntos_salvacion = puntos_limite + 1

        # Calcular los puntos máximos posibles
        puntos_maximos_posibles = pts_temporada_24 + (3 * len(fechas_unicas))
        
        if puntos_maximos_posibles < puntos_salvacion:
            print(f"El equipo {equipo_a_salvar} no puede salvarse por si mismo")
        else:
            print(f"El equipo {equipo_a_salvar} necesita al menos {puntos_salvacion:.2f} puntos para salvarse.")
    else:
        # El solver no encontró solución: el equipo ya está salvado
        print(f"El equipo {equipo_a_salvar} no tiene forma de descender.")




    # Una vez obtenido el valor de la funcion objetivo que indica la maxima cantidad de puntos que puede hacer el equipo y aun descender
    # buscamos el equipo que le sigue en puntos ya que si superamos ese equipo nos salvamos del descenso.

    # if status == pywraplp.Solver.OPTIMAL:
    #     # Imprimir valor de la función objetivo
    #     print(f"\nValor de la función objetivo (Puntos máximos para {equipo_a_salvar}): {solver.Objective().Value()}")
        
    #     # Crear lista de resultados
    #     resultados = []
    #     for equipo in equipos:
    #         # Buscar los puntos previos en el dataframe original
    #         puntos_previos = promedios_df.loc[promedios_df['Equipo'] == equipo, '24'].values[0]
            
    #         total = total_anual[equipo].solution_value()
    #         promedio = promedio_temporadas[equipo].solution_value()
    #         desc_tabla = B_tabla[equipo].solution_value()
    #         desc_promedio = B_promedio[equipo].solution_value()
            
    #         resultados.append({
    #             'Equipo': equipo,
    #             'Puntos Previos': puntos_previos,
    #             'Puntos Totales': total,
    #             'Puntos Nuevos': total - puntos_previos,
    #             'Promedio': round(promedio, 2),
    #             'Desciende por Tabla': desc_tabla == 1,
    #             'Desciende por Promedio': desc_promedio == 1
    #         })
        
    #     # Ordenar por puntos totales de menor a mayor
    #     resultados_ordenados = sorted(resultados, key=lambda x: x['Puntos Totales'])
        
    #     # Imprimir tabla
    #     print("\n" + "=" * 110)
    #     print(f"{'TABLA DE DESCENSO':^110}")
    #     print("=" * 110)
    #     print(f"{'Equipo':<15}{'Puntos Previos':>15}{'Puntos Totales':>15}{'Puntos Nuevos':>15}{'Promedio':>15}{'Desc. Tabla':>15}{'Desc. Promedio':>15}")
    #     print("-" * 110)
        
    #     for resultado in resultados_ordenados:
    #         print(f"{resultado['Equipo']:<15}{resultado['Puntos Previos']:>15.2f}{resultado['Puntos Totales']:>15.2f}{resultado['Puntos Nuevos']:>15.2f}{resultado['Promedio']:>15.2f}{resultado['Desciende por Tabla']:>15}{resultado['Desciende por Promedio']:>15}")
        
    #     print("\n" + "=" * 110)
    #     print("\nEquipos que descienden:")
        
    #     # Listar equipos que descienden
    #     desc_tabla = [r['Equipo'] for r in resultados if r['Desciende por Tabla']]
    #     desc_promedio = [r['Equipo'] for r in resultados if r['Desciende por Promedio']]
        
    #     print("Por Tabla:")
    #     for equipo in desc_tabla:
    #         print(f"- {equipo}")
        
    #     print("\nPor Promedio:")
    #     for equipo in desc_promedio:
    #         print(f"- {equipo}")
    # else:
    #     print("No se encontró una solución óptima.")