# EASQAA

Error analysis of SAR question-answering agents (package and command: `sarqa`).
The single source of truth is [SPEC.md](SPEC.md).

## Setup

```bash
conda create -n easqaa python=3.10
conda activate easqaa
pip install -e ".[dev]"        # add ".[detector]" for torch/torchvision
pytest -m "not data and not gpu"
```

HRSID goes under `data/hrsid/` (not tracked). See `docs/data_notes.md`.
