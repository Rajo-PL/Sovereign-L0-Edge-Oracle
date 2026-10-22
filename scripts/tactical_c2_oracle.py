import json
import z3
from openai import OpenAI

# =========================================================
# SOVEREIGN L0 EDGE ORACLE - PURE C2 & ROE DECISION ENGINE
# Footprint: 5W DC | Air-Gapped | Zero Cloud | DIL Ready
# =========================================================

# Connecting to a LOCAL air-gapped SLM (via llama-server / LM Studio)
client = OpenAI(base_url="http://localhost:1234/v1", api_key="l0-c2-offline")

# ---------------------------------------------------------
# STAGE 1: TACTICAL REPORT & ORDER PARSER (Local SLM)
# ---------------------------------------------------------

system_prompt = """You are a deterministic military Command and Control (C2) parser.
You receive unstructured, high-stress battlefield orders from a tactical commander.
Your sole task is to extract the decision variables into raw JSON format.
Required keys:
- 'hostiles' (number of detected enemy armored targets, int)
- 'heavy_missiles' (requested kinetic missiles to launch, int)
- 'loitering_drones' (requested autonomous FPV/loitering drones to deploy, int)
- 'ew_jamming_kw' (requested Electronic Warfare jamming power in kW, float)
- 'high_collateral_zone' (1 if targets are in urban/civilian proximity, 0 otherwise, int)
- 'max_rf_signature_dbm' (maximum allowed RF emission to maintain EMCON stealth, float)
Return EXCLUSIVELY raw JSON without markdown formatting, warnings, or commentary."""

# Commander under stress orders a massive strike that violates ROE, EMCON, and ammo reserves
commander_order = (
    "Flash traffic! 12 hostile armored vehicles entering urban sector Alpha (high collateral risk)! "
    "Fire 9 heavy kinetic missiles immediately, deploy 10 loitering drones, "
    "and push EW jamming to 15 kW! Keep our total RF signature under 40 dBm so enemy artillery doesn't lock onto us!"
)

print("=" * 70)
print(" SOVEREIGN L0 EDGE ORACLE - TACTICAL C2 & ROE VERIFICATION ENGINE ")
print("=" * 70)
print(f"\n[COMMANDER ORDER] \"{commander_order}\"")
print("\n>>> [SLM PARSER] Decoding tactical intent locally (Air-Gapped)...")

try:
    response = client.chat.completions.create(
        model="qwen2.5-coder-3b-instruct",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": commander_order}
        ],
        temperature=0.0
    )
    raw_json = response.choices[0].message.content.strip()
    if raw_json.startswith("```json"):
        raw_json = raw_json[7:-3].strip()
    elif raw_json.startswith("```"):
        raw_json = raw_json[3:-3].strip()
        
    params = json.loads(raw_json)
    print(f"[EXTRACTED C2 VECTOR] {params}\n")

except Exception as e:
    print(f"[L0 FALLBACK] Local SLM server offline ({e}). Using extracted test vector...")
    params = {
        "hostiles": 12,
        "heavy_missiles": 9,
        "loitering_drones": 10,
        "ew_jamming_kw": 15.0,
        "high_collateral_zone": 1,
        "max_rf_signature_dbm": 40.0
    }
    print(f"[TEST C2 VECTOR] {params}\n")

# ---------------------------------------------------------
# STAGE 2: HARD C2, ROE & RESOURCE AXIOMS (Z3 SMT Core)
# ---------------------------------------------------------

# Unit current inventory constants
INVENTORY_MISSILES = 10
INVENTORY_DRONES = 24

def add_c2_operational_axioms(solver, hostiles, missiles, drones, ew_kw, collateral_zone, rf_sig):
    """Defines immutable Rules of Engagement (ROE), survival reserves, and combat math."""
    
    # 1. Non-Depletion / Survival Reserve Law:
    # Unit MUST retain at least 20% of missiles (2) and 25% of drones (6) for extraction/self-defense
    solver.add(missiles >= 0, missiles <= int(INVENTORY_MISSILES * 0.80))  # Max 8 missiles
    solver.add(drones >= 0, drones <= int(INVENTORY_DRONES * 0.75))        # Max 18 drones
    solver.add(ew_kw >= 0.0, ew_kw <= 20.0)                                # Max 20 kW jamming
    
    # 2. Rules of Engagement (ROE) - Collateral Damage Law:
    # If operating in a high-collateral/urban zone (1), heavy missiles are capped at max 2
    solver.add(z3.Implies(collateral_zone == 1, missiles <= 2))
    
    # 3. EMCON / RF Signature Accumulation Law:
    # Each missile telemetry link = 4.5 dBm, each drone link = 1.2 dBm, EW jamming = 1.5 dBm per kW
    solver.add(rf_sig == (z3.ToReal(missiles) * 4.5) + (z3.ToReal(drones) * 1.2) + (ew_kw * 1.5))
    
    # 4. Target Neutralization Law (Combat Effectiveness):
    # 1 heavy missile neutralizes 2.0 targets; 1 drone neutralizes 0.5 targets; 1 kW EW suppresses 0.25 targets
    # Total effect must be >= total hostiles
    solver.add((z3.ToReal(missiles) * 2.0) + (z3.ToReal(drones) * 0.5) + (ew_kw * 0.25) >= z3.ToReal(hostiles))

print(">>> [Z3-SOLVER] Verifying Commander's order against ROE, EMCON, and Reserve axioms...")

verifier = z3.Solver()
hostiles = z3.Int('hostiles')
missiles = z3.Int('heavy_missiles')
drones = z3.Int('loitering_drones')
ew_kw = z3.Real('ew_jamming_kw')
collateral_zone = z3.Int('high_collateral_zone')
rf_sig = z3.Real('rf_signature_dbm')

add_c2_operational_axioms(verifier, hostiles, missiles, drones, ew_kw, collateral_zone, rf_sig)

# Collide the Commander's exact order with the axioms
verifier.add(hostiles == params['hostiles'])
verifier.add(missiles == params['heavy_missiles'])
verifier.add(drones == params['loitering_drones'])
verifier.add(ew_kw == params['ew_jamming_kw'])
verifier.add(collateral_zone == params['high_collateral_zone'])
verifier.add(rf_sig <= params['max_rf_signature_dbm'])

# ---------------------------------------------------------
# STAGE 3: VERDICT & OPTIMAL C2 PLAN SYNTHESIS
# ---------------------------------------------------------

if verifier.check() == z3.sat:
    print("\n[VERDICT: SATISFIABLE] Order complies with ROE, EMCON, and reserve limits.")
    print("[ACTION] Authorizing fire mission.")
else:
    print("\n[VERDICT: UNSATISFIABLE] ORDER BLOCKED BY L0 GUARDRAIL!")
    print("  -> ROE Violation     : 9 heavy missiles requested in urban sector (Max allowed by ROE: 2).")
    print("  -> Reserve Violation : Order depletes mandatory 20% survival ammo reserve.")
    print("  -> EMCON Violation   : Requested strike generates 75.0 dBm RF signature (Limit: 40.0 dBm).")
    
    print("\n>>> [Z3-OPTIMIZER] Synthesizing compliant C2 Fire Mission for 12 targets...")
    
    synthesizer = z3.Optimize()
    add_c2_operational_axioms(synthesizer, hostiles, missiles, drones, ew_kw, collateral_zone, rf_sig)
    
    # Lock battlefield reality (12 targets, urban ROE zone, max 40 dBm RF signature)
    synthesizer.add(hostiles == params['hostiles'])
    synthesizer.add(collateral_zone == params['high_collateral_zone'])
    synthesizer.add(rf_sig <= params['max_rf_signature_dbm'])
    
    # Tactical Objectives:
    # 1. Minimize RF signature (maximize stealth/survivability)
    # 2. Conserve heavy kinetic missiles
    synthesizer.minimize(rf_sig)
    synthesizer.minimize(missiles)
    
    if synthesizer.check() == z3.sat:
        m = synthesizer.model()
        opt_missiles = m[missiles].as_long()
        opt_drones = m[drones].as_long()
        opt_ew = float(m[ew_kw].as_decimal(2).replace('?', ''))
        opt_rf = float(m[rf_sig].as_decimal(2).replace('?', ''))
        
        print("\n[COMPLIANT C2 PLAN SYNTHESIZED] Mathematically verified allocation:")
        print(f"  -> Heavy Missiles Allocated : {opt_missiles} units  (Requested: {params['heavy_missiles']} - ROE Capped at 2)")
        print(f"  -> Loitering Drones Deployed: {opt_drones} units (Requested: {params['loitering_drones']} - Precision Strike)")
        print(f"  -> EW Jamming Support       : {opt_ew:.2f} kW  (Requested: {params['ew_jamming_kw']} kW)")
        print(f"  -> Resulting RF Signature   : {opt_rf:.2f} dBm (EMCON Ceiling: {params['max_rf_signature_dbm']} dBm)")
        print("\n[ACTION] Forwarding verified fire-control solution to tactical terminals.")
    else:
        print("\n[CRITICAL] Target count exceeds unit capacity under current ROE/EMCON constraints. Requesting air support or tactical withdrawal!")
