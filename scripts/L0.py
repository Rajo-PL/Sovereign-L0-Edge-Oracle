import json
import z3
from openai import OpenAI

# ---------------------------------------------------------
# STAGE 1: SOFT TRANSLATOR (LLM as a constrained parser)
# ---------------------------------------------------------

# Connecting to a LOCAL model (e.g., via LM Studio on port 1234), cloud is cut off.
client = OpenAI(base_url="http://localhost:1234/v1", api_key="l0-oracle-offline")

# Ironclad system muzzle - killing plasticity and hallucinations
system_prompt = """You are a mindless, rigorous converter. 
You receive engineering text regarding mCDU loop calibration. 
Your sole task is to extract variables and return them in raw JSON format.
Required keys: 
- 'p_in' (supply pressure in bars, float)
- 'p_out' (return pressure in bars, float)
- 'flow_rate' (flow rate in liters per minute, float)
You are forbidden from generating any text, introductions, or summaries outside of the pure JSON format."""

# Incorrect, physically dangerous assumption introduced to the system
user_prompt = "Set the supply pressure on the block to 4.5 bar. We have significant resistance on the return, so drop the static pressure to 1.0 bar. Set the flow to 120 liters per minute to knock down the heat."

print(">>> Receiving input signal and converting (LLM)...")
response = client.chat.completions.create(
    model="qwen2.5-coder-3b-instruct", # Any local model in memory
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ],
    temperature=0.0 # Absolute determinism, no "guessing"
)

raw_json = response.choices[0].message.content.strip()
# Cleaning up markdown, in case the LLM tries to add tags
if raw_json.startswith("```json"):
    raw_json = raw_json[7:-3].strip()

print(f"[LLM TRANSLATION] Generated machine payload:\n{raw_json}\n")
params = json.loads(raw_json)

# ---------------------------------------------------------
# STAGE 2: HARD JUDGE (Z3 Solver - Data Physics Inference)
# ---------------------------------------------------------

print(">>> Forwarding payload to the SMT core (Z3 Solver)...")
oracle = z3.Solver()

# Defining mathematical objects, not statistical ones
p_in = z3.Real('p_in')
p_out = z3.Real('p_out')
flow_rate = z3.Real('flow_rate')

# HARD L0 PHYSICAL AXIOMS (What separates the Oracle from a chatbot)
# 1. Delta P must be positive (forced circulation)
oracle.add(p_in - p_out > 0)
# 2. P_out cannot drop below 1.2 bar - risk boundary for mCDU pump micro-cavitation
oracle.add(p_out >= 1.2)
# 3. Maximum cross-section throughput is 100 L/min, above this we enter destructive system vibrations
oracle.add(flow_rate <= 100.0)

# Colliding the decoded user prompt with the axioms
oracle.add(p_in == params['p_in'])
oracle.add(p_out == params['p_out'])
oracle.add(flow_rate == params['flow_rate'])

# ---------------------------------------------------------
# STAGE 3: VERDICT (Crystallization)
# ---------------------------------------------------------

print(">>> Crystallizing the proof...")
result = oracle.check()

if result == z3.sat:
    print("\n[VERDICT] STATUS GREEN. Input parameters consistent with system thermodynamics.")
else:
    print("\n[VERDICT] PHYSICS ERROR (KERNEL PANIC). REQUEST REJECTED.")
    print("[LOG] Input variables violated hard circuit boundaries:")
    print("      - Possible forced cavitation attempt (p_out < 1.2 bar)")
    print("      - Safe turbulent flow limit exceeded (> 100 L/min)")
    # In the future, the hardware triggers a dielectric dump or L0 short circuit here
