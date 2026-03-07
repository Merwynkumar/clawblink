"""ClawBlink CLI entry point."""

import typer

app = typer.Typer(name="clawblink", help="ClawBlink AI CLI")


@app.command()
def hello(name: str = typer.Argument("World", help="Name to greet")):
    """Say hello."""
    typer.echo(f"Hello, {name}!")


@app.command()
def version():
    """Show version."""
    from clawblink import __version__
    typer.echo(f"clawblink {__version__}")


def main():
    app()


if __name__ == "__main__":
    main()
