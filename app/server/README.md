Blind Charging API Server
===

## Code generation

All of the code in `./generated` is generated from code in `./schema`.

To run code generation, make sure you have the `fastapi-codegen` repo cloned.
Note that until Pydantic2 support is merged into the main project,
we need to use [Joe's fork of the repo](https://github.com/jnu/fastapi-code-generator).

```
poetry run python -m fastapi_code_generator -i ../../stanford-policylab/bc2/app/server/schema/api.yaml -o ../../stanford-policylab/bc2/app/server/generated -r -t ../../stanford-policylab/bc2/app/server/schema/templates -d pydantic_v2.BaseModel -p 3.11
```

### Implementations

Code generation takes care of stubs for the API routes.
To write the implementations,
add corresponding functions in `./handlers`.
