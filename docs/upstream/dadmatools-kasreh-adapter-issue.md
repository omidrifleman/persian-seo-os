---
title: "kasreh pipeline leaves XLM-R task adapters randomly initialized (adapter load never applies)"
---

### Summary

When running `Pipeline("tok,kasreh")` on DadmaTools 2.3.6, the XLM-RoBERTa **pfeiffer task adapter** registered as `'embedding'` stays at **random init**. Kasreh token labels then depend on the process RNG at `Pipeline()` construction time (deterministic within a process, unstable across processes).

### Bug A — wrong `model_name` + early-return

In `language.py`, `_kasreh_doc` calls:

```python
self._load_adapter_weights(model_name='ner')
```

But `_load_adapter_weights` starts with:

```python
if model_name not in self.pipelines:
    return
```

For `pipelines == ['tok', 'kasreh']`, `'ner'` is not present → **immediate return**, zero adapter keys copied into `_embedding_layers`.

### Bug B — needle does not match checkpoint key names

`_load_adapter_weights` only copies keys containing `adapters.{model_name}.adapter`.

For kasreh that is `adapters.kasreh.adapter`.

Actual keys inside `persian.kasreh.mdl` → `adapters` look like:

```text
xlmr.encoder.layer.N.output.layer_text_task_adapters.ner.adapter_down.0.weight
```

Match counts when instrumented:

| weights source | needle | matched |
| --- | --- | --- |
| tokenizer checkpoint | `adapters.tokenizer.adapter` | 48 / 50 |
| kasreh checkpoint | `adapters.kasreh.adapter` | **0 / 53** |
| kasreh checkpoint | `adapters.ner.adapter` | 48 / 53 |

So even `model_name='kasreh'` would still copy **zero** embedding adapters.

`Base_Model.__init__` always `add_adapter('embedding')`, creating random pfeiffer weights that are never replaced for kasreh.

### Evidence (seed)

With `random` / `numpy` / `torch` seeded immediately before `Pipeline()`:

| seed | labels on «کتاب علی» (5 fresh processes) |
| --- | --- |
| 0, 1, 2 | `[('کتاب','S-kasreh'),('علی','O')]` |
| **3** | `[('کتاب','O'),('علی','O')]` — **5/5** |

Same seed → same labels; different seeds → different labels. Within one process, 200 identical forwards; all modules `.training is False`.

### Reproduction

```python
import random
import numpy as np
import torch
import dadmatools.pipeline.language as language

CACHE = "/absolute/path/to/dadmatools/cache"

def run(seed: int):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    nlp = language.Pipeline("tok,kasreh", cache_dir=CACHE, gpu=False)
    doc = nlp("کتاب علی")
    return [(t.text, getattr(getattr(t, "_", None), "kasreh", None)) for t in doc]

print(run(0))
print(run(3))
```

### Expected

Kasreh checkpoint task adapters should be remapped onto the active `'embedding'` adapter before kasreh inference, with a key pattern matching `layer_text_task_adapters.<task>.*`, without requiring `'ner'` in `pipelines`.

### Environment

- `dadmatools[full]==2.3.6`
- torch CPU
