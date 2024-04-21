import psse34
import psspy
import pandas as pd
import pyomo.environ as pe


def despacho_economico(cost_file, cuts):
    # obtener la demanda
    ierr, (demanda_aparente,) = psspy.aloadcplx(sid=-1, flag=1, string="MVAACT")
    demanda = sum([s.real for s in demanda_aparente])
    
    # parametros de generadores
    ierr, (gen_bus,) = psspy.agenbusint(sid=-1, flag=1, string="NUMBER")
    ierr, (pmax, pmin, pgen) = psspy.agenbusreal(sid=-1, flag=1, string=["PMAX", "PMIN", "PGEN"])
    generator_data = pd.DataFrame()
    generator_data["BUS"] = gen_bus
    generator_data["PMAX"] = pmax
    generator_data["PMIN"] = pmin
    generator_data["PGEN"] = pgen
    generator_data = generator_data.set_index("BUS")

    cost = pd.read_csv(cost_file)
    generator_data = generator_data.join(cost.set_index("GENBUS")).dropna()
    
    # modelo de optimizacion
    m = pe.ConcreteModel()
    m.G = pe.Set(initialize=generator_data.index)
    def generator_bounds(m, i):
        return generator_data.loc[i]["PMIN"], generator_data.loc[i]["PMAX"]
    m.pg = pe.Var(m.G, bounds=generator_bounds)
    
    # objetivo
    m.objective = pe.Objective(
        expr=sum(generator_data.COST[i] * m.pg[i] for i in generator_data.index),
        sense=pe.minimize
        )
    
    # restricciones
    def balance_potencia(m):
        return sum(m.pg[i] for i in m.G) == demanda
    m.balance_potencia = pe.Constraint(rule=balance_potencia)
    
    # resolver
    opt = pe.SolverFactory("appsi_highs")
    log = opt.solve(m, tee=True)
    
    # update case
    for gen_bus, generator in generator_data.iterrows():
        new_pg = m.pg[gen_bus].value
        incremental_change = new_pg - generator.PGEN
        psspy.bsys(1,0,[0.0,0.0],0,[],1,[gen_bus],0,[],0,[])
        psspy.scal_2(1,0,1,[0,0,0,0,0],[0.0,0.0,0.0,0.0,0.0,0.0,0.0])
        psspy.scal_2(0,1,2,[_i,3,1,1,0],[0.0, incremental_change,0.0,0.0,0.0,0.0,0.0])
    psspy.fdns([0,0,0,1,0,0,0,0])

