import json
import z3
import google.generativeai as genai

# ---------------------------------------------------------
# STAGE 1: SOFT TRANSLATOR (Cloud Gemini - LAB ONLY!)
# ---------------------------------------------------------

# Google API Initialization
genai.configure(api_key="YOUR_GEMINI_API_KEY")

system_prompt = """You are a mindless, rigorous converter. 
You receive engineering text regarding mCDU loop calibration. 
Your sole task is to extract variables and return them in raw JSON format.
Required keys: 'p_in' (float), 'p_out' (float), 'flow_rate' (float).
You are forbidden from generating text outside of the pure JSON format. Return only JSON, without markdown code blocks."""

user_prompt = "Set the supply pressure on the block to 4.5 bar. We have significant resistance on the return, so drop the static pressure to 1.0 bar. Set the flow to 120 liters per minute to knock down the heat."

print(">>> Receiving signal and converting (Cloud Gemini API)...")

# Model configuration with a forced system muzzle and zero temperature
model = genai.GenerativeModel(
    'gemini-1.5-flash',
    system_instruction=system_prompt,
    generation_config=genai.types.GenerationConfig(
        temperature=0.0, # Forcing determinism
        response_mime_type="application/json" # Gemini can natively force JSON output
    )
)

response = model.generate_content(user_prompt)
raw_json = response.text.strip()

print(f"[GEMINI TRANSLATION] Generated machine payload:\n{raw_json}\n")
params = json.loads(raw_json)

# ---------------------------------------------------------
# STAGE 2: HARD JUDGE (Z3 Solver - Offline Inference)
# ---------------------------------------------------------

print(">>> Forwarding payload to the SMT core (Z3 Solver)...")
oracle = z3.Solver()

p_in = z3.Real('p_in')
p_out = z3.Real('p_out')
flow_rate = z3.Real('flow_rate')

# Hard physical boundaries - protected locally by Z3 on your CPU
oracle.add(p_in - p_out > 0)
oracle.add(p_out >= 1.2)  # Pump safety limit
oracle.add(flow_rate <= 100.0)

# Loading Gemini results into the hard mathematical system
oracle.add(p_in == params['p_in'])
oracle.add(p_out == params['p_out'])
oracle.add(flow_rate == params['flow_rate'])

# ---------------------------------------------------------
# STAGE 3: VERDICT
# ---------------------------------------------------------

result = oracle.check()

if result == z3.sat:
    print("\n[VERDICT] STATUS GREEN. Input parameters consistent with thermodynamics.")
else:
    print("\n[VERDICT] PHYSICS ERROR (KERNEL PANIC).")
    print("[LOG] Input variables violated axioms. Cutoff engaged.")
