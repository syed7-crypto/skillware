import os

import pytest
import yaml

from .skill import TOSEvaluatorSkill


@pytest.fixture
def skill():
    return TOSEvaluatorSkill()


@pytest.fixture
def manifest():
    manifest_path = os.path.join(os.path.dirname(__file__), "manifest.yaml")
    with open(manifest_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_skill_manifest_consistency(skill, manifest):
    skill_manifest = skill.manifest
    assert skill_manifest["name"] == manifest["name"]
    assert skill_manifest["version"] == manifest["version"]


def test_skill_execution_requires_inputs(skill):
    result = skill.execute({})
    assert "error" in result
    assert "target_url" in result["error"]
