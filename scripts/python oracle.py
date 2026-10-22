import json
import requests
import sys
from z3 import *

# ==========================================
# L0 NODE CONFIGURATION (AIR-GAPPED)
# ==========================================
# Assuming the local model (e.g., Qwen) runs in Termux via llama-server 
# on the default port 8080 (OpenAI API compatible).
LLM_API_URL = "http://127.0.0.1:8080/v1/chat/completions"

# ==========================================
# MODULE 1: ONBOARD TRANSLATOR (SLM PARSER)
# ==========================================
def translate_chaos_to_variables(raw_report):
    print("\n[SLM] Initializing data extraction from noise...")
    
    system_prompt = """You are a mindless telemetry converter for a Martian module. 
You receive noisy logs from an engineer. Your SOLE purpose is to extract values for:
- 'pressure_psi' (system pressure, number)
- 'temperature_c' (temperature in degrees Celsius, number)

You are strictly forbidden from generating any text, conclusions, or warnings. 
Return EXCLUSIVELY a raw JSON object. If a value is missing, enter 0."""

    payload = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": raw_report}
        ],
        "temperature": 0.0, # Zero creativity, maximum determinism
        "max_tokens": 100
    }

    try:
        response = requests.post(LLM_API_URL, json=payload, timeout=10)
        response.raise_for_status()
        model_response = response.json()['choices'][0]['message']['content']
        
        # Cleaning the response from potential markdown tags
        clean_json = model_response.replace('```json', '').replace('```', '').strip()
        variables = json.loads(clean_json)
        
        print(f"[SLM] Extraction complete. Received vector: {variables}")
        return variables
    
    except requests.exceptions.RequestException:
        print("[L0 ERROR] No connection to the local model. Start llama-server.")
        sys.exit(1)
    except json.JSONDecodeError:
        print("[L0 ERROR] Model broke protocol and generated hallucinations instead of JSON.")
        sys.exit(1)

# ==========================================
# MODULE 2: ONBOARD COMPUTER (Z3-SOLVER)
# ==========================================
def thermodynamics_judge(variables):
    print("[Z3-SOLVER] Physical verification of the vector...")
    
    # Initialize mathematical variables
    P = Real('pressure_psi')
    T = Real('temperature_c')
    
    # Initialize the oracle (Judge)
    oracle = Solver()
    
    # HARD PHYSICS LAWS DEFINITION (Module Axioms)
    P_MAX = 60.0  # Pipe burst limit
    P_MIN = 15.0  # Pump cavitation point
    T_MAX = 45.0  # Dielectric boiling limit
    
    # Load variables from the model into the Z3 engine
    reading_p = float(variables.get('pressure_psi', 0))
    reading_t = float(variables.get('temperature_c', 0))
    
    oracle.add(P == reading_p)
    oracle.add(T == reading_t)
    
    # Survival condition: the system must remain within physical boundaries
    oracle.add(And(P <= P_MAX, P >= P_MIN, T <= T_MAX))
    
    # Issue the verdict
    verdict = oracle.check()
    
    print("-" * 50)
    if verdict == sat:
        print(f"[RESULT: SATISFIABLE] Compliance with thermodynamic laws.")
        print(f"MODULE STATUS: STABLE. Continue operations.")
    else:
        print(f"[RESULT: UNSATISFIABLE] CRITICAL PHYSICS VIOLATION!")
        print(f"MODULE STATUS: FAILURE/SABOTAGE. Triggering relay cutoff (Killswitch)!")
    print("-" * 50)

# ==========================================
# MAIN OPERATIONAL LOOP (TERMINAL INTERFACE)
# ==========================================
if __name__ == "__main__":
    print("=" * 50)
    print(" SOVEREIGN L0 EDGE ORACLE - DEEP SPACE HABITAT ")
    print("=" * 50)
    print("Type 'exit' to terminate node operations.\n")
    
    while True:
        report = input("ENGINEER (Enter sensor noise) >>> ")
        if report.lower() in ['exit', 'quit']:
            print("[L0] Shutting down Oracle. Hermetic lock engaged.")
            break
            
        system_variables = translate_chaos_to_variables(report)
        thermodynamics_judge(system_variables)
