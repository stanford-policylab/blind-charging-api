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

## Database

### Driver

Install the MS ODBC driver for your operating system, for example using these instructions:

https://learn.microsoft.com/en-us/sql/connect/odbc/linux-mac/install-microsoft-odbc-driver-sql-server-macos?view=sql-server-ver16

### Start a dev database

You can develop against a MS SQL database running in Docker:

```bash
docker run \
    --platform linux/amd64 \
    --name bc2-mssql \
    -e "ACCEPT_EULA=Y" \
    -e "MSSQL_SA_PASSWORD=bc2Password" \
    -p 1433:1433 \
    -d mcr.microsoft.com/mssql/server:2022-latest
```
