from skillware.core.loader import SkillLoader


def test_pii_masker_manifest():
    bundle = SkillLoader.load_skill("compliance/pii_masker")
    assert bundle["manifest"]["name"] == "compliance/pii_masker"
    assert "text" in bundle["manifest"]["parameters"]["properties"]
    assert "mode" in bundle["manifest"]["parameters"]["properties"]


def test_pii_masker_modes(mocker):
    bundle = SkillLoader.load_skill("compliance/pii_masker")
    skill_class = bundle["module"].PIIMaskerSkill
    skill = skill_class()

    # Mock the Ollama API call
    mock_response = (
        "Hello [PERSON_1], your wallet [CRYPTO_ADDRESS] and [EMAIL] have been verified."
    )
    # The _call_ollama method returns (sanitized_text, [entities])
    mocker.patch.object(
        skill,
        "_call_ollama",
        return_value=(mock_response, ["PERSON_1", "CRYPTO_ADDRESS", "EMAIL"]),
    )

    # Test Mask mode (default)
    result_mask = skill.execute(
        {
            "text": "Hello John Doe, your wallet 0xabc and john@doe.com have been verified."
        }
    )
    expected_text = (
        "Hello [PERSON_1], your wallet [CRYPTO_ADDRESS] and [EMAIL] have been verified."
    )
    assert result_mask["sanitized_text"] == expected_text
    assert "PERSON" in result_mask["metadata"]["detected_entities"]
    assert "CRYPTO_ADDRESS" in result_mask["metadata"]["detected_entities"]

    # Test Redact mode
    result_redact = skill.execute(
        {
            "text": "Hello John Doe, your wallet 0xabc and john@doe.com have been verified.",
            "mode": "redact",
        }
    )
    assert (
        result_redact["sanitized_text"]
        == "Hello XXXX, your wallet XXXX and XXXX have been verified."
    )

    # Test Remove mode
    result_remove = skill.execute(
        {
            "text": "Hello John Doe, your wallet 0xabc and john@doe.com have been verified.",
            "mode": "remove",
        }
    )
    # Remove simple mode removes the tags. It cleans spaces around them.
    assert (
        result_remove["sanitized_text"] == "Hello , your wallet and have been verified."
    )
