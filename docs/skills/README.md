# Skill Library

Welcome to the official catalog of Skillware capabilities.

### Office
Skills for document processing, email automation, and productivity.

| Skill | ID | Description |
| :--- | :--- | :--- |
| **[PDF Form Filler](pdf_form_filler.md)** | `office/pdf_form_filler` | Fills AcroForm-based PDFs by mapping user instructions to detected form fields using LLM-based semantic understanding. |

## Finance
Tools for financial analysis, blockchain interaction, and regulatory compliance.

| Skill | ID | Description |
| :--- | :--- | :--- |
| **[Wallet Screening](wallet_screening.md)** | `finance/wallet_screening` | Comprehensive risk assessment for Ethereum wallets. Checks sanctions lists (OFAC, FBI) and identifies interactions with malicious contracts (Mixers, Scams). |


## Optimization
Middleware skills that operate on text or state to increase performance, security, or efficiency.

| Skill | ID | Description |
| :--- | :--- | :--- |
| **[Prompt Token Rewriter](prompt_rewriter.md)** | `optimization/prompt_rewriter` | Aggressively compresses massive prompts or context histories while retaining semantic meaning to save tokens. |

## Data Engineering
Skills tailored for generating, parsing, and orchestrating large datasets for machine learning or analytics workflows.

| Skill | ID | Description |
| :--- | :--- | :--- |
| **[Synthetic Data Generator](synthetic_generator.md)** | `data_engineering/synthetic_generator` | Generates high-entropy structured synthetic data for model fine-tuning to avoid mode collapse. |

## Compliance
Enforces privacy, guardrails, and secure handling of sensitive data before it reaches external endpoints.

| Skill | ID | Description |
| :--- | :--- | :--- |
| **[PII Masker](pii_masker.md)** | `compliance/pii_masker` | High-precision, local PII (Personally Identifiable Information) detection and redaction using the micro-f1-mask model. |
| **[MiCA Module](mica_module.md)** | `compliance/mica_module` | Self-contained local Policy Enforcement and RAG engine strictly adhering to MiCA crypto-asset regulation. |
| **[Terms of Service Evaluator](tos_evaluator.md)** | `compliance/tos_evaluator` | Local-first evaluation of robots.txt and website legal pages to decide whether an intended automated action appears permissible. |

---

## Installing Skills

Skills are included in the `skillware/skills` directory. To use them:

```python
from skillware.core.loader import SkillLoader

# Load by ID (path relative to skills dir)
skill = SkillLoader.load_skill("finance/wallet_screening")
```
