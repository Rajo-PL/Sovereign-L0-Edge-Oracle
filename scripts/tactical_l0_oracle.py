import json
import sys
import z3
from openai import OpenAI

# =========================================================
# SOVEREIGN L0 EDGE ORACLE - TACTICAL C2 / DIL EDITION
# Operating Footprint: 5W DC | Air-Gapped | Zero RF (EMCON)
# =========================================================

# Connecting to a LOCAL air-gapped SLM (via llama-server / LM Studio)
client = OpenAI(base_url="http://localhost:1234/v1", api_key="l0-tactical-offline")

# ---------------------------------------------------------
# STAGE 1: COMBAT OVERRIDE PARSER (Constrained Local SLM)
# ---------------------------------------------------------

system_prompt = """You are a deterministic tactical telemetry and command parser for a mobile AESA radar and liquid-cooled Electronic Warfare (EW) unit.
You receive high-stress, unstructured operator voice-to-text commands under combat conditions.
Your sole task is to extract target operational parameters and return them in raw JSON format.
Required keys:
- 'radar_power_kw' (requested RF/radar output power in kW, float)
- 'coolant_flow_lpm' (requested liquid cooling loop flow in L/min, float)
- 'generator_load_kw' (maximum allowed tactical microgrid/generator power in kW, float)
- 'acoustic_limit_db' (maximum allowed acoustic signature for stealth/EMCON in dB, float)
Return EXCLUSIVELY raw JSON without markdown blocks, warnings, or commentary."""

# Operator under fire issues a conflicting, physically destructive command
combat_command = (
    "Contact bearing 045! Boost AESA radar array to 60 kW immediately! "
    "We are in acoustic stealth sector, cap acoustic signature at 65 dB, "
    "throttle tactical generator down to 45 kW, and limit coolant pump flow to 50 L/min!"
)

print("=" * 65)
print(" SOVEREIGN L0 EDGE ORACLE - TACTICAL C2 & MICROGRID GUARDRAIL ")
print("=" * 65)
print(f"\n[OPERATOR OVERRIDE] \"{combat_command}\"")
print("\n>>> [SLM PARSER] Extracting state vector in EMCON (Radio Silence) mode...")

try:
    response = client.chat.completions.create(
        model="qwen2.5-coder-3b-instruct",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": combat_command}
        ],
        temperature=0.0
    )
    raw_json = response.choices[0].message.content.strip()
    if raw_json.startswith("```json"):
        raw_json = raw_json[7:-3].strip()
    elif raw_json.startswith("```"):
        raw_json = raw_json[3:-3].strip()
        
    params = json.loads(raw_json)
    print(f"[SLM VECTOR] {params}\n")

except Exception as e:
    print(f"[L0 FALLBACK] Local SLM offline ({e}). Loading hardcoded test vector for Z3 verification...")
    params = {
        "radar_power_kw": 60.0,
        "coolant_flow_lpm": 50.0,
        "generator_load_kw": 45.0,
        "acoustic_limit_db": 65.0
    }
    print(f"[TEST VECTOR] {params}\n")

# ---------------------------------------------------------
# STAGE 2: TACTICAL DATA PHYSICS AXIOMS (Z3 SMT Core)
# ---------------------------------------------------------

def add_tactical_physics_axioms(solver, r_pwr, c_flow, gen_pwr, noise_db):
    """Defines immutable thermodynamic, electrical, and acoustic stealth laws for the mobile unit."""
    # 1. Hardware physical boundaries
    solver.add(r_pwr >= 10.0, r_pwr <= 80.0)       # Radar operational range (kW)
    solver.add(c_flow >= 20.0, c_flow <= 120.0)    # Liquid cooling mCDU pump limits (L/min)
    solver.add(gen_pwr >= 15.0, gen_pwr <= 100.0)  # Tactical hybrid generator limits (kW)
    
    # 2. Solid-State Radar Thermal Dissipation Law:
    # Requires at least 1.5 L/min of dielectric coolant flow per 1 kW of radar power to prevent array meltdown
    solver.add(c_flow >= (r_pwr * 1.5))
    
    # 3. Tactical Microgrid Power Balance Law:
    # Generator must cover Radar Power + Cooling Pump hydraulic power (0.05 kW per 1 L/min of flow)
    solver.add(gen_pwr >= (r_pwr + (c_flow * 0.05)))
    
    # 4. Acoustic & Thermal Stealth Coupling Law (dB signature model):
    # Base chassis noise is 45 dB + 0.25 dB per kW of generator load + 0.10 dB per L/min of pump flow
    solver.add(noise_db == (45.0 + (gen_pwr * 0.25) + (c_flow * 0.10)))

print(">>> [Z3-SOLVER] Verifying combat command against coupled thermo-electrical & stealth axioms...")

verifier = z3.Solver()
r_pwr = z3.Real('radar_power_kw')
c_flow = z3.Real('coolant_flow_lpm')
gen_pwr = z3.Real('generator_load_kw')
noise_db = z3.Real('acoustic_db')

add_tactical_physics_axioms(verifier, r_pwr, c_flow, gen_pwr, noise_db)

# Inject operator's requested parameters
verifier.add(r_pwr == params['radar_power_kw'])
verifier.add(c_flow == params['coolant_flow_lpm'])
verifier.add(gen_pwr == params['generator_load_kw'])
verifier.add(noise_db <= params['acoustic_limit_db'])

# ---------------------------------------------------------
# STAGE 3: VERDICT & COMBAT ENVELOPE SYNTHESIS
# ---------------------------------------------------------

if verifier.check() == z3.sat:
    print("\n[VERDICT: SATISFIABLE] Command complies with physics and stealth limits.")
    print("[ACTION] Committing setpoints to tactical PLC.")
else:
    print("\n[VERDICT: UNSATISFIABLE] COMMAND BLOCKED! Hardware destruction or stealth breach imminent.")
    print("  -> Reason: 60 kW radar output at 50 L/min flow will melt the solid-state transmitter")
    print("     and exceed the 45 kW generator cap and 65 dB stealth envelope.")
    print("\n>>> [Z3-OPTIMIZER] Synthesizing MAXIMUM combat radar power within the 65 dB stealth limit...")
    
    synthesizer = z3.Optimize()
    add_tactical_physics_axioms(synthesizer, r_pwr, c_flow, gen_pwr, noise_db)
    
    # Lock the commander's mandatory stealth ceiling (e.g., <= 65 dB), leave hardware setpoints as unknowns
    synthesizer.add(noise_db <= params['acoustic_limit_db'])
    
    # Combat Objective: Maximize radar detection power without violating stealth or melting the array
    synthesizer.maximize(r_pwr)
    synthesizer.minimize(gen_pwr)
    
    if synthesizer.check() == z3.sat:
        m = synthesizer.model()
        opt_radar = float(m[r_pwr].as_decimal(2).replace('?', ''))
        opt_flow = float(m[c_flow].as_decimal(2).replace('?', ''))
        opt_gen = float(m[gen_pwr].as_decimal(2).replace('?', ''))
        opt_noise = float(m[noise_db].as_decimal(2).replace('?', ''))
        
        print("\n[COMBAT ENVELOPE SYNTHESIZED] Optimal survivable configuration computed:")
        print(f"  -> Max Safe Radar Power   : {opt_radar:.2f} kW   (Requested: {params['radar_power_kw']} kW)")
        print(f"  -> Required Coolant Flow  : {opt_flow:.2f} L/min (Requested: {params['coolant_flow_lpm']} L/min)")
        print(f"  -> Tactical Generator Load: {opt_gen:.2f} kW   (Requested: {params['generator_load_kw']} kW)")
        print(f"  -> Acoustic Signature     : {opt_noise:.2f} dB   (Stealth Ceiling: {params['acoustic_limit_db']} dB)")
        print("\n[ACTION] Overrides applied to local controller. Array protected, stealth maintained.")
    else:
        print("\n[CRITICAL] Stealth ceiling incompatible with minimum radar idle power. Dropping to standby!")
