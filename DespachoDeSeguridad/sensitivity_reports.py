import re
import textwrap
from io import StringIO
import psse34
import psspy
import pandas as pd


def get_blocks(string):
    "Encuentra bloques de datos"
    # block = r"(?<=\sSENSITIVITY FACTORS OF)(.*?)(?=-{80})"
    block = r"(?<=SENSITIVITY FACTORS OF)(.*?)(?=SENSITIVITY FACTORS OF)"
    blocks = re.finditer(block, string, re.DOTALL)
    return map(lambda x: x.group(), blocks)


def sentivity_variable(string):
    "Encuentra el tipo de sensibilidad MW, MVAR, pu"
    pattern = r"(?<=\()(.*?)(?=\))"
    m = re.search(pattern, string)
    return m.group(0)
    
    
def element_type(string):
    "Encuentra al tipo de objeto al que se le calcula la sensibilidad"
    element_type = string.split("(")[0].strip()
    if "3WNDTR" in string:
        element_type = "3WNDTR"
    return element_type
    
    
def element_id(string, element_type):
    "Devuelve el id del elemento"
    if element_type == "BRANCH FLOW":
        busi = re.search("(?:ON\s+)(\d+)", string).group(1)
        busj = re.search("(?:TO\s+)(\d+)", string).group(1)
        ckt = re.search("(\S+)(?:\s+MORE)", string).group(1)
        identifier = (busi, busj, ckt)
        
    elif element_type == "3WNDTR":
        busi = re.search("(?:ON\s+)(\d+)", string).group(1)
        name = re.search("(?:TO 3WNDTR\s+)(\d+)", string).group(1)
        ckt = re.search("(\S+)(?:\s+MORE)", string).group(1)
        identifier = (busi, name, ckt)
        
    elif "BUS" in element_type:
        busi = re.search("(?:AT THE BUS\s+)(\d+)", string).group(1)
        identifier = busi
        
    else:
        raise ValueError(f"Invalid element_type, got {element_type}")
    
    return identifier
    
    
def get_tables(string):
    tables = re.split(r"\n\n", string)
    tables = [t for t in tables[1:] if t]
    return tables
       
       
def read_table(string, element_type):
    BUS = "<--------- BUS NAME -------->"
    GENBUS = "<------ GENERATOR BUS ------>"
    LOADBUS = "<-------- LOAD BUS --------->"
    TAP = "<--------------- TAP CHANGING TRANSFORMERS -------------->"
    
    BRANCH_COLS = {
        "BUS": [(1, 31), (33, 41)],
        "GENBUS": [(0, 30), (30, 38), (38, 48), (48, 58), (58, 67)],
        "LOADBUS": [(1, 31), (33, 42), (45, 53)],
        "TAP": [(1, 60), (60, 63), (65, 72), (74, 81), (83, 90), (92, 99)],
    }

    BUS_COLS = {
        "BUS": [(1, 31), (33, 41), (41, 51)],
        "GENBUS": [(1, 31), (31, 40), (40, 49), (49, 58), (59, 67)],
        "LOADBUS": [(1, 31), (33, 42), (42, 53), (56, 64), (65, 75)],
        "TAP": [(1, 60), (60, 63), (65, 72), (74, 81), (83, 90), (92, 99)],
    }
    
    COLS = {"branch": BRANCH_COLS, "bus": BUS_COLS}
    
    # Encuentro tipo de tabla
    element_type = "branch" if element_type in ["BRANCH FLOW", "3WNDTR"] else "bus"
        
    if BUS in string:
        table_type = "BUS"        
    elif  GENBUS in string:
        table_type = "GENBUS"
    elif  LOADBUS in string:
        table_type = "LOADBUS"
    elif  TAP in string:
        table_type = "TAP"
    else:
        raise ValueError(f"Type of table not found:\n{string}")
    
    file = StringIO(string)
    table = pd.read_fwf(file, colspecs=COLS[element_type][table_type])
    return table
    
    
def read_sensitivity_report(filename):
    with open(filename) as f:                                                   # minimo preprocesamiento
        string = f.read()
        string = re.sub("^\r\n", "", string)
        
    opposing_system = re.search("(\s+)(.*)(\s+)(IS USED FOR OPPOSING)", string).group(2)
    group_of_tables = []
    for block in get_blocks(string):
        element = element_type(block)
        variable = sentivity_variable(block)
        identifier = element_id(block, element)

        for table in get_tables(block):
            df = read_table(table, element)

            if isinstance(identifier, str):
                df["BUS"] = identifier
            else:
                df["BUSI"] = int(identifier[0])
                df["BUSJ"] = int(identifier[1])
                df["CKT"] = identifier[2].ljust(2)
            
            df["VARIABLE"] = variable
            df["OPPO SYS"] = opposing_system
            df.columns = ["GENERATOR BUS"] + df.columns[1:].to_list()           # ajusto columnas de generacion con numero de barra y no extended bus
            df["GENERATOR BUS"] = df["GENERATOR BUS"].map(lambda s: int(s.split()[0]))                      
            group_of_tables += [df]                                             # sumo la tabla que se quiere imprimir    
            
    return pd.concat(group_of_tables, ignore_index=True)


def get_sensitivities(case, con_isv):
    with open(case + ".sub") as f:
        sub_file = f.read()

    sensitivities = []
    for re_match in re.findall("(SUBSYSTEM )'(GEN.*)'", sub_file):
        system = re_match[-1]                                                   # generador al cual calcular sensibilidad         
        oppo_system = "OPPOSING_" + system                                      # generadores contrarios
        psspy.report_output(2,f"{case}_{con_isv}.rprt",[0,0])                   # cambio el tipo de reporte para capturarlo
        psspy.sensitivity_flows(                                                # calculo sensibilidad
            [1,2],
            [0,1,0,0,0,0,0,2,1],
            [ 0.1, 0.1],
            [system, oppo_system, case],
            case + ".dfx"
        )
        psspy.report_output(1,"",[0,0])                                         # devuelvo el reporte a su condicion original
        sensitivity = read_sensitivity_report(f"{case}_{con_isv}.rprt")         # leo el reporte
        sensitivities.append(sensitivity)

    return pd.concat(sensitivities, ignore_index=True)
