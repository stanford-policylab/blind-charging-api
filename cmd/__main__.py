import typer

from .provision import init_provision_cli

cli = typer.Typer()

init_provision_cli(cli)


if __name__ == "__main__":
    cli()
