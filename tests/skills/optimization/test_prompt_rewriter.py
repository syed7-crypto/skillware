from skillware.core.loader import SkillLoader


def get_skill():
    bundle = SkillLoader.load_skill("optimization/prompt_rewriter")
    return bundle["module"].PromptRewriter()


def test_manifest_schema():
    skill = get_skill()
    manifest = skill.manifest
    assert manifest.get("name") == "optimization/prompt_rewriter"
    assert manifest.get("version") == "0.1.0"


def test_rewriter_execution_low():
    skill = get_skill()
    params = {
        "raw_text": "This   is a    very\n\n\nspaced out  prompt.",
        "compression_aggression": "low",
    }
    result = skill.execute(params)
    assert result["compressed_text"] == "This is a very spaced out prompt."
    assert result["original_tokens"] >= result["new_tokens"]


def test_rewriter_execution_high():
    skill = get_skill()
    params = {
        "raw_text": "Please make sure to read this and analyze the data.",
        "compression_aggression": "high",
    }
    result = skill.execute(params)
    assert "Please" not in result["compressed_text"]
    assert "make sure to" not in result["compressed_text"]
    assert result["tokens_saved"] > 0
    assert "new_tokens" in result
    assert "original_tokens" in result


def test_empty_string():
    skill = get_skill()
    result = skill.execute({"raw_text": ""})
    assert "error" in result
    assert result["error"] == "raw_text cannot be empty."
