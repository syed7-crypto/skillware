import pytest
from skillware.core.loader import SkillLoader


def test_load_skill_not_found():
    with pytest.raises(FileNotFoundError):
        SkillLoader.load_skill("nonexistent_skill_path_12345")


def test_to_ollama_prompt():
    dummy_bundle = {
        "manifest": {
            "name": "test_ollama_skill",
            "description": "A very useful test skill.",
            "parameters": {
                "type": "object",
                "properties": {
                    "arg1": {"type": "string", "description": "The first arg"}
                },
                "required": ["arg1"]
            }
        }
    }

    prompt = SkillLoader.to_ollama_prompt(dummy_bundle)
    assert "### Tool: `test_ollama_skill`" in prompt
    assert "**Description:** A very useful test skill." in prompt
    assert "- `arg1` (string): The first arg [Required]" in prompt


def test_to_gemini_tool():
    dummy_bundle = {
        "manifest": {
            "name": "test_gemini_skill",
            "parameters": {
                "type": "object",
                "properties": {
                    "param1": {"type": "string"}
                }
            }
        }
    }
    tool = SkillLoader.to_gemini_tool(dummy_bundle)
    assert tool["name"] == "test_gemini_skill"
    # Gemini requires UPPERCASE types for Protobufs
    assert tool["parameters"]["type"] == "OBJECT"
    assert tool["parameters"]["properties"]["param1"]["type"] == "STRING"


def test_to_claude_tool():
    dummy_bundle = {
        "manifest": {
            "name": "test_claude_skill",
            "description": "desc",
            "parameters": {
                "type": "object",
                "properties": {"arg_claude": {"type": "string"}}
            }
        }
    }
    tool = SkillLoader.to_claude_tool(dummy_bundle)
    assert tool["name"] == "test_claude_skill"
    assert tool["input_schema"]["type"] == "object"


def test_sanitize_openai_tool_name():
    assert (
        SkillLoader._sanitize_openai_tool_name("compliance/tos_evaluator")
        == "compliance_tos_evaluator"
    )
    assert SkillLoader._sanitize_openai_tool_name("wallet_screening") == "wallet_screening"
    assert SkillLoader._sanitize_openai_tool_name("") == "unknown_tool"
    assert SkillLoader._sanitize_openai_tool_name("a" * 80).startswith("a")
    assert len(SkillLoader._sanitize_openai_tool_name("a" * 80)) == 64


def test_to_openai_tool():
    dummy_bundle = {
        "manifest": {
            "name": "compliance/tos_evaluator",
            "description": "Evaluate site policy.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_url": {"type": "string", "description": "URL"}
                },
                "required": ["target_url"],
            },
        }
    }
    tool = SkillLoader.to_openai_tool(dummy_bundle)
    assert tool["type"] == "function"
    assert tool["function"]["name"] == "compliance_tos_evaluator"
    assert tool["function"]["description"] == "Evaluate site policy."
    assert tool["function"]["parameters"]["type"] == "object"
    assert "target_url" in tool["function"]["parameters"]["properties"]
