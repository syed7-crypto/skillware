import json
import os

import google.generativeai as genai

from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()

bundle = SkillLoader.load_skill("compliance/tos_evaluator")
print(f"Loaded Skill: {bundle['manifest']['name']}")

TOSEvaluatorSkill = bundle["module"].TOSEvaluatorSkill
tos_skill = TOSEvaluatorSkill()

genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
tools = [SkillLoader.to_gemini_tool(bundle)]

model = genai.GenerativeModel(
    "gemini-2.5-flash-lite",
    tools=tools,
    system_instruction=bundle["instructions"],
)

chat = model.start_chat(enable_automatic_function_calling=True)
user_query = (
    "Before scraping Hackernoon tagged AI pages, check whether automated crawling "
    "appears allowed for https://hackernoon.com/tagged/ai."
)
print(f"User: {user_query}")

response = chat.send_message(user_query)
while response.candidates and response.candidates[0].content.parts:
    part = response.candidates[0].content.parts[0]
    if not part.function_call:
        break

    fn_name = part.function_call.name
    fn_args = dict(part.function_call.args)
    print(f"Gemini requested tool: {fn_name}")
    print(f"Input: {fn_args}")

    if fn_name == "compliance/tos_evaluator":
        result = tos_skill.execute(fn_args)
        print(json.dumps(result, indent=2))
        response = chat.send_message(
            [
                {
                    "function_response": {
                        "name": fn_name,
                        "response": {"result": result},
                    }
                }
            ]
        )
    else:
        break

print("\nFinal Response:")
print(response.text)
