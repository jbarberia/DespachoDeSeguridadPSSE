import re
import zipfile
import itertools
import pyomo.environ as pe
import pandas as pd
import psse34
import psspy
import pssarrays
_i = psspy.getdefaultint()
_f = psspy.getdefaultreal()
_s = psspy.getdefaultchar()

def crear_dfax(case):
    psspy.dfax_2(
        [1,1,1],
        "{}.sub".format(case),
        "{}.mon".format(case),
        "{}.con".format(case),
        "{}.dfx".format(case)
    )
    
    
def correr_accc(case):
    psspy.accc_with_dsp_3(
        0.1,
        [0,0,0,1,1,1,0,0,0,0,1],
        case,
        "{}.dfx".format(case),
        "{}.acc".format(case),
        "",
        "",
        "{}.zip".format(case)
    )
    
    contingencias_isv = extraer_mapeo_zip_accc(case)
    rslt = {
        "zipfile": "{}.zip".format(case),
        "contingencies": contingencias_isv
    }
    return rslt


def extraer_mapeo_zip_accc(case):
    # Encuentro mapeo de caso incremental para cada contingencia
    zip_file_obj = zipfile.ZipFile("{}.zip".format(case), 'r')
    name_file = zip_file_obj.read('Names.phy').decode()
    strings = re.findall(r'[^\x00-\x1F\x7F-\xFF]+', name_file)[1:]
    contingency_identificator = [
        (label, isv.strip()) for label, isv in zip(strings[::2], strings[1::2])
    ]
    return contingency_identificator


def obtener_transferencias():
    """obtiene las transferencias por las lineas"""
    ierr, (i, j) = psspy.abrnint(string=["FROMNUMBER", "TONUMBER"])
    ierr, (ckt,) = psspy.abrnchar(string=["ID"])
    ierr, (flow, rate) = psspy.abrnreal(string=["MAXMVA", "RATE"])
    
    return i, j, ckt, flow, rate


def calcular_riesgo(c=1.0):
    """devuelve el riesgo y un mapeo de sobrecargas en lineas"""
    sobrecarga = 0
    sobrecargas = {}
    transferencias = obtener_transferencias()
    for i, j, ckt, flow, rate in zip(*transferencias):
        sobrecargas[i, j, ckt] = max(0, flow - rate)
        sobrecarga += max(0, flow - rate)
    riesgo = sobrecarga * c
    return riesgo, sobrecargas
    
    
def calcular_sensibilidad(case, identificador_linea):
    # calcular_sensibilidad('IEEE14', (1, 2, '1'))
    "Genera una tabla con la sensibilidad para cada generador"
    ierr, (gen_buses,) = psspy.agenbusint(string="NUMBER")
    ierr, (pmax,) = psspy.agenbusreal(string="PMAX")
    gen_buses = [bus for bus, pmax in zip(gen_buses, pmax) if pmax > 0]

    results = []
    for gen_bus in gen_buses:
        i, j, ckt = identificador_linea
        rslt = pssarrays.sensitivity_flow_to_mw(
            ibus=i, jbus=j, ckt=ckt,
            mainsys=case,
            netmod="ac",
            dfxfile="{}.dfx".format(case),
            brnflowtyp="mva",
            transfertyp="import",
            oppsystyp="subsystem",
            dispmod=1,
            oppsys="OPPOSING_GEN{}".format(gen_bus)
        )
        
        # genero tabla de datos
        df = pd.DataFrame(rslt['genvalues']).T        
        df.index = df.index.map(lambda ext_bus: int(ext_bus.strip().split()[0]))
        df["gen"] = df.index        
        df["oppsys"] = gen_bus
        results.append(df)
        
    return pd.concat(results, axis=0).reset_index(drop=True)


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


# MAIN
CASE = "IEEE14"
SAV_FILE = "{}.sav".format(CASE)
COST_FILE = "{}.cost".format(CASE)
ZIP_FILE = "{}.zip".format(CASE)

# -----------------------------------------------------------------------------
psspy.psseinit()
psspy.case(SAV_FILE)    
# despacho_economico(COST_FILE, cuts=[])
crear_dfax(CASE)
rslt = correr_accc(CASE)

# ------------------------------------------------------------------------------
riesgo_total = 0
sensibilidades = []
for con_id, con_isv in rslt["contingencies"]:   
    psspy.getcontingencysavedcase(ZIP_FILE, "InitCase")
    psspy.getcontingencysavedcase(ZIP_FILE, con_isv)
    # assert psspy.solved() == 0 # TODO: poner un factor por caso no resuelto
    if not psspy.solved() == 0:
        continue
    riesgo, sobrecargas = calcular_riesgo()    
    riesgo_total += riesgo
    
    lineas_sobrecargadas = [identifier for identifier, sobrecarga in sobrecargas.items() if sobrecarga > 0.0]
    for identificador_linea in lineas_sobrecargadas:
        sensibilidad = calcular_sensibilidad(CASE, identificador_linea)
        sensibilidad = sensibilidad[sensibilidad.gen == sensibilidad.oppsys]
        sensibilidad['con_id'] = con_id
        sensibilidades.append(sensibilidad)
    
cuts = pd.concat(sensibilidades, axis=0).reset_index(drop=True)
# ------------------------------------------------------------------------------


