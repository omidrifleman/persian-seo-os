# Upstream report: DadmaTools kasreh embedding adapters never load (v2.3.6)

**Target repo:** https://github.com/Dadmatech/DadmaTools  
**Affects:** `dadmatools==2.3.6` (`Pipeline("tok,kasreh")`)

## Title (for GitHub issue)

`kasreh` pipeline leaves XLM-R task adapters randomly initialized (adapter load never applies)

## Body

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

Even if this called `model_name='kasreh'`, `'kasreh'` is in `pipelines`, but see Bug B.

### Bug B — needle does not match checkpoint key names

`_load_adapter_weights` only copies keys containing:

```text
adapters.{model_name}.adapter
```

For kasreh that is `adapters.kasreh.adapter`.

Actual keys inside `persian.kasreh.mdl` → `adapters` are named like:

```text
xlmr.encoder.layer.N.output.layer_text_task_adapters.ner.adapter_down.0.weight
```

Instrumenting the match loop:

| weights source | needle | matched |
| --- | --- | --- |
| tokenizer checkpoint | `adapters.tokenizer.adapter` | 48 / 50 (substring hits `…task_adapters.tokenizer.adapter…`) |
| kasreh checkpoint | `adapters.kasreh.adapter` | **0 / 53** |
| kasreh checkpoint | `adapters.ner.adapter` | 48 / 53 |

So even a corrected `model_name='kasreh'` would still copy **zero** embedding adapters.

Meanwhile `Base_Model.__init__` always does `add_adapter(task_name)` with `task_name='embedding'`, creating random pfeiffer weights that are never replaced for kasreh.

### Evidence (seed)

Before any workaround, with `random`/`numpy`/`torch` seeded immediately before `Pipeline()`:

| seed | labels on «کتاب علی» (5 fresh processes) |
| --- | --- |
| 0, 1, 2 | `[('کتاب','S-kasreh'),('علی','O')]` — pass |
| **3** | `[('کتاب','O'),('علی','O')]` — **fail, all 5/5** |

Same seed → same labels across processes; different seeds → different labels. Mean/first element of  
`xlmr.encoder.layer.0.output.layer_text_task_adapters.embedding.adapter_down.0.weight`  
differ between seed 0 and seed 3 after build+infer.

Within one process, 200 identical forwards → **no** train-mode dropout issue (`.training` is False everywhere).

### Reproduction

```python
import random
import numpy as np
import torch
import dadmatools.pipeline.language as language

CACHE = "/path/to/dadmatools/cache"  # absolute, with models prefetched

def run(seed: int):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    nlp = language.Pipeline("tok,kasreh", cache_dir=CACHE, gpu=False)
    doc = nlp("کتاب علی")
    return [(t.text, getattr(getattr(t, "_", None), "kasreh", None)) for t in doc]

print(run(0))
print(run(3))  # often all-O while seed 0 is S-kasreh/O
```

Also note `_load_adapter_weights('ner')` is invoked on first kasreh infer even though `ner` ∉ pipelines.

### Expected

Kasreh checkpoint task adapters should be remapped onto the active `'embedding'` adapter (or the adapter name used at `add_adapter` time) before kasreh inference, with a key pattern that matches `layer_text_task_adapters.<task>.*`, and without requiring `'ner'` to be listed in `pipelines` for the kasreh path.

### Environment

- `dadmatools[full]==2.3.6`
- torch CPU
- Windows / Linux both reproduce cross-process label flips without seeding
