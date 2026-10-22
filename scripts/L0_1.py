import json
import z3
from openai import OpenAI

# ---------------------------------------------------------
# STAGE 1: CONSTRAINED PARSER (Human-in-the-Loop / Log Gateway)
# ---------------------------------------------------------

# Connecting to a LOCAL air-gapped model (e.g., via llama-server / LM Studio)
client = OpenAI(base_url="http://localhost:1234/v1", api_key="l0-oracle-offline")

system_prompt = """You are a rigorous telemetry and command converter for an mCDU cooling loop. 
You receive unstructured operator override commands or fault logs. 
Your sole task is to extract target setpoints and return them in raw JSON format.
Required keys: 
- 'p_in' (target supply pressure in bar, float)
- 'p_out' (target return pressure in bar, float)
- 'flow_rate' (target flow rate in L/min, float)
- 'thermal_load_kw' (current heat load to dissipate in kW, float)
Return EXCLUSIVELY raw JSON without markdown formatting or commentary."""

# Operator issues a dangerous override during a thermal spike
user_prompt = (
    "Emergency override: Rack thermal load is at 85 kW. "
    "Set supply pressure to 4.5 bar, drop return static pressure to 1.0 bar to overcome resistance, "
    "and push flow rate to 120 L/min immediately."
)

print(">>> [SLM GATEWAY] Parsing unstructured operator override...")
response = client.chat.completions.create(
    model="qwen2.5-coder-3b-instruct",
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ],
    temperature=0.0
)

raw_json = response.choices[0].message.content.strip()
if raw_json.startswith("```json"):
    raw_json = raw_json[7:-3].strip()

print(f"[SLM OUTPUT] Extracted state vector:\n{raw_json}\n")
params = json.loads(raw_json)

# ---------------------------------------------------------
# STAGE 2: HARD JUDGE & SETPOINT SYNTHESIZER (Z3 SMT Core)
# ---------------------------------------------------------

def add_mCDU_physics_axioms(solver, p_in, p_out, flow, q_load):
    """Defines immutable physical and hydraulic laws for the mCDU secondary loop."""
    # 1. Anti-cavitation boundary: suction/return pressure must stay >= 1.2 bar
    solver.add(p_out >= 1.2)
    # 2. Structural pipe rating: max supply pressure <= 5.5 bar
    solver.add(p_in <= 5.5)
    # 3. Erosion/vibration boundary: max flow rate <= 100.0 L/min
    solver.add(flow <= 100.0, flow >= 20.0)
    # 4. Hydraulic loop coupling: Delta P must match flow resistance ( simplified linear/quadratic constraint )
    # Minimum 0.03 bar pressure drop per 1 L/min of flow
    solver.add((p_in - p_out) >= (flow * 0.03))
    # 5. Thermodynamic dissipation requirement: Flow must be sufficient for the thermal load (kW)
    # Assuming dielectric/water heat capacity requires at least 1.1 L/min per 1 kW for safe Delta T
    solver.add(flow >= (q_load * 1.1))

print(">>> [Z3-SOLVER] Verifying proposed command against coupled mCDU physics...")
verifier = z3.Solver()

p_in = z3.Real('p_in')
p_out = z3.Real('p_out')
flow_rate = z3.Real('flow_rate')
thermal_load = z3.Real('thermal_load_kw')

# Load physical laws
add_mCDU_physics_axioms(verifier, p_in, p_out, flow_rate, thermal_load)

# Collide operator request with physics
verifier.add(p_in == params['p_in'])
verifier.add(p_out == params['p_out'])
verifier.add(flow_rate == params['flow_rate'])
verifier.add(thermal_load == params['thermal_load_kw'])

# ---------------------------------------------------------
# STAGE 3: VERDICT & MATHEMATICAL FALLBACK SYNTHESIS
# ---------------------------------------------------------

if verifier.check() == z3.sat:
    print("\n[VERDICT: SATISFIABLE] Command complies with coupled thermo-hydraulics.")
    print("[ACTION] Forwarding setpoints to PLC registers.")
else:
    print("\n[VERDICT: UNSATISFIABLE] COMMAND BLOCKED! Physics / Cavitation violation detected.")
    print(">>> [Z3-SYNTHESIS] Computing nearest mathematically safe fallback setpoints for current thermal load...")
    
    # Initialize a clean SMT solver to synthesize valid parameters for the given heat load
    synthesizer = z3.Optimize()
    add_mCDU_physics_axioms(synthesizer, p_in, p_out, flow_rate, thermal_load)
    
    # Lock the actual thermal load from the rack, but leave p_in, p_out, and flow_rate as symbolic unknowns!
    synthesizer.add(thermal_load == params['thermal_load_kw'])
    
    # Objective: Minimize pump stress (supply pressure) while satisfying all thermal & cavitation laws
    synthesizer.minimize(p_in)
    synthesizer.minimize(flow_rate)
    
    if synthesizer.check() == z3.sat:
        safe_model = synthesizer.model()
        safe_p_in = float(safe_model[p_in].as_decimal(2).replace('?', ''))
        safe_p_out = float(safe_model[p_out].as_decimal(2).replace('?', ''))
        safe_flow = float(safe_model[flow_rate].as_decimal(2).replace('?', ''))
        
        print("\n[FALLBACK SYNTHESIZED] Safe operational envelope found:")
        print(f"  -> Safe Supply Pressure (p_in) : {safe_p_in} bar (Requested: {params['p_in']} bar)")
        print(f"  -> Safe Return Pressure (p_out): {safe_p_out} bar (Requested: {params['p_out']} bar - Cavitation Risk!)")
        print(f"  -> Safe Flow Rate              : {safe_flow} L/min (Requested: {params['flow_rate']} L/min)")
        print("[ACTION] Ready to commit synthesized safe setpoints to PLC.")
    else:
        print("\n[CRITICAL] Thermal load exceeds physical loop capacity. Triggering graceful hardware trip!")
