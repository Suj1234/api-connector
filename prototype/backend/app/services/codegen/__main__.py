"""python -m app.services.codegen: regenerate connectors/examples/ from specs/examples/."""

from app.services.codegen import PROTOTYPE, write_examples

for path in write_examples():
    print(path.relative_to(PROTOTYPE))
