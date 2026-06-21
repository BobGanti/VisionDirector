# VisionDirector

VisionDirector is a pluggable SyntaxMatrix module.

Host usage:

```python
from smx_visiondirector import setup_visiondirector

setup_visiondirector(
    app=app,
    project_root=PROJECT_ROOT,
    init_schema=True,
    ai_profile=VISIONDIRECTOR_AGENTS_PROFILES,
)
```

The host builds AI provider clients and passes them through `ai_profile`.
VisionDirector must not instantiate model/provider clients independently.
