"""Load and manage Buddhi determination prompts."""

from pathlib import Path

import yaml


def load_buddhi_prompt(config_dir: str | Path) -> str:
    """Load the Buddhi system prompt from config/buddhi_prompt.yaml."""
    config_path = Path(config_dir) / "buddhi_prompt.yaml"
    with open(config_path) as f:
        config = yaml.safe_load(f)

    prompt = config["system"]

    # Phase 5: append learned guidelines from Adhyavasāya
    learned = config.get("learned_guidelines", [])
    if learned:
        prompt += "\n\nLearned guidelines from experience:\n"
        for guideline in learned:
            prompt += f"- {guideline}\n"

    return prompt
