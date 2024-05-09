Blind Charging Server
===

## Code gen

Most of the code is generated from an OpenAPI schema. (See `./schema`.)

To run code gen, make sure you have the `fastapi-codegen` package installed globally, and then run:

```
fastapi-codegen -i schema/api.yaml -o generated -r -t schema/templates -p 3.11 -d pydantic_v2.BaseModel
```
